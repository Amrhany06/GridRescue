"""Reusable Spark transformations for the conditionally approved experimental target."""
import os
import sys
import csv
from datetime import datetime, timedelta
from pyspark.sql import SparkSession, functions as F, Window

KEY = ['fips_code', 'timestamp']
SOURCE = ['fips_code', 'county', 'state', 'customers_out', 'run_start_time']
PREDICTORS = ['customers_out_t','lag_15m','lag_60m','delta_60m',
              'rolling_mean_60m','rolling_variance_60m','history_slots_60m',
              'hour_utc','weekday_utc','month_utc']


def make_spark(name='GridRescue'):
    """Start or reuse a named local Spark session with a consistent UTC clock."""
    os.environ.setdefault('PYSPARK_PYTHON',sys.executable)
    os.environ.setdefault('PYSPARK_DRIVER_PYTHON',sys.executable)
    os.environ.setdefault('SPARK_LOCAL_IP','127.0.0.1')
    spark=(SparkSession.builder.master('local[2]').appName(name)
           .config('spark.sql.session.timeZone','UTC')
           .config('spark.sql.legacy.timeParserPolicy','CORRECTED')
           .config('spark.sql.shuffle.partitions','4')
           .config('spark.driver.memory','2g')
           .config('spark.ui.enabled','false').getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    return spark


def read_source(spark, paths):
    """Check each CSV header and return the original five source fields as strings."""
    # String ingestion preserves original tokens and leading zeros for quarantine.
    for path in paths:
        with open(path,newline='',encoding='utf-8-sig') as stream:
            if next(csv.reader(stream))!=SOURCE:
                raise ValueError(f'Unexpected source header: {path}')
    df=spark.read.option('header',True).option('mode','FAILFAST').schema(', '.join(c+' string' for c in SOURCE)).csv([str(p) for p in paths])
    return df


def clean(raw):
    """Return clean unique reports, quarantined rows and a reconciliation ledger."""
    # Safe parsing returns null for a bad token so the report can be quarantined.
    parsed=(raw.withColumn('timestamp',F.expr("try_to_timestamp(run_start_time, 'yyyy-MM-dd HH:mm:ss')"))
            .withColumn('_count',F.expr('try_cast(customers_out as bigint)')))
    conditions=[(~F.col('fips_code').rlike('^[0-9]{5}$'),'invalid_fips'),
                (F.col('timestamp').isNull() | (~F.col('run_start_time').rlike(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')),'invalid_timestamp'),
                (F.col('timestamp').isNotNull() & (F.unix_timestamp('timestamp') % 900 != 0),'off_grid_timestamp'),
                ((~F.col('customers_out').rlike('^[0-9]+$')) | F.col('_count').isNull(),'invalid_count'),
                (F.col('county').isNull() | F.col('state').isNull(),'missing_geography')]
    reasons=[F.when(F.coalesce(cond,F.lit(True)),F.lit(reason)) for cond,reason in conditions]
    parsed=parsed.withColumn('reason',F.concat_ws('|',*reasons)).cache()
    invalid=parsed.filter("reason != ''")
    valid=parsed.filter("reason = ''").drop('reason').cache()
    distinct=valid.dropDuplicates(SOURCE).cache()
    # Each remaining repeated key contains multiple distinct source rows.
    conflicts=distinct.groupBy(*KEY).count().filter('count > 1').select(*KEY)
    conflict_rows=distinct.join(conflicts,KEY,'inner').cache()
    # A left anti join keeps only source rows without a matching conflict key.
    silver=(distinct.join(conflicts,KEY,'left_anti').drop('customers_out')
            .withColumnRenamed('_count','customers_out').cache())
    stats=dict(raw=raw.count(),invalid=invalid.count(),exact_duplicates_removed=valid.count()-distinct.count(),conflict_rows=conflict_rows.count(),silver=silver.count())
    assert stats['raw']==sum(stats[k] for k in ['invalid','exact_duplicates_removed','conflict_rows','silver'])
    rejected=invalid.unionByName(conflict_rows.withColumn('reason',F.lit('conflicting_key')))
    # The caller can persist outputs; retain only useful caches.
    parsed.unpersist(); valid.unpersist(); distinct.unpersist()
    return silver,rejected,stats


def features(silver):
    """Return clean anchors with exact lags, past-hour summaries and UTC calendar fields."""
    base=(silver.withColumn('epoch',F.unix_timestamp('timestamp'))
          .withColumnRenamed('customers_out','customers_out_t'))
    # The range is in seconds because epoch, the ordering column, is in seconds.
    w=Window.partitionBy('fips_code').orderBy('epoch').rangeBetween(-3600,0)
    out=(base.withColumn('rolling_mean_60m',F.avg('customers_out_t').over(w))
         .withColumn('rolling_variance_60m',F.var_pop('customers_out_t').over(w))
         .withColumn('history_slots_60m',F.count('*').over(w)))
    for minutes in [15,60]:
        # Shift each historical lookup key forward to match its future anchor exactly.
        history=base.select('fips_code',(F.col('epoch')+minutes*60).alias('epoch'),F.col('customers_out_t').alias(f'lag_{minutes}m'))
        out=out.join(history,['fips_code','epoch'],'left')
    return (out.withColumn('delta_60m',F.col('customers_out_t')-F.col('lag_60m'))
            .withColumn('hour_utc',F.hour('timestamp')).withColumn('weekday_utc',F.dayofweek('timestamp'))
            .withColumn('month_utc',F.month('timestamp')))


def split_tag(timestamp):
    """Return the partition for one UTC anchor after excluding split-crossing labels."""
    end=timestamp+timedelta(hours=3)
    if any(timestamp < boundary <= end for boundary in [datetime(2021,1,1),datetime(2022,1,1),datetime(2023,1,1)]):
        return 'purged'
    return 'train' if 2018<=timestamp.year<=2020 else 'validation' if timestamp.year==2021 else 'test' if timestamp.year==2022 else 'excluded'


def audit_labels(gold):
    """Return Gold anchors with complete-window labels, coverage diagnostics and split tags."""
    # Start at t+15m to exclude the current outage reading from future outcomes.
    future=Window.partitionBy('fips_code').orderBy('epoch').rangeBetween(900,10800)
    # Clean rows are unique and grid-aligned, so 12 rows means all 12 slots were observed.
    out=(gold.withColumn('future_slots',F.count('*').over(future))
         .withColumn('future_last_epoch',F.max('epoch').over(future))
         .withColumn('future_max',F.max('customers_out_t').over(future))
         .withColumn('escalation_threshold',F.col('customers_out_t')+F.greatest(F.lit(200.0),F.col('customers_out_t')*0.5))
         .withColumn('label_complete',F.col('future_slots')==12)
         .withColumn('candidate_y',F.when((F.col('customers_out_t')>0)&F.col('label_complete'),(F.col('future_max')>=F.col('escalation_threshold')).cast('int'))))
    # Include anchor, all observed future gaps, and the gap to the horizon endpoint.
    previous=Window.partitionBy('fips_code').orderBy('epoch')
    with_gaps=gold.select('fips_code','epoch').withColumn('_previous_epoch',F.lag('epoch').over(previous))
    with_gaps=with_gaps.withColumn('_gap_seconds',F.col('epoch')-F.col('_previous_epoch'))
    gap_audit=with_gaps.withColumn('_max_future_gap',F.max('_gap_seconds').over(future)).select('fips_code','epoch','_max_future_gap')
    out=out.join(gap_audit,['fips_code','epoch'],'left').withColumn('future_max_gap_seconds',F.greatest(F.col('_max_future_gap'),F.col('epoch')+10800-F.coalesce(F.col('future_last_epoch'),F.col('epoch')))).drop('_max_future_gap')
    year=F.year('timestamp')
    crosses=F.lit(False)
    # Exclude a label if its last possible observation is on or across a split boundary.
    for boundary in ['2021-01-01','2022-01-01','2023-01-01']:
        crosses=crosses | ((F.col('timestamp')<F.to_timestamp(F.lit(boundary))) & (F.col('timestamp')+F.expr('INTERVAL 3 HOURS')>=F.to_timestamp(F.lit(boundary))))
    return out.withColumn('split',F.when(crosses,'purged')
                         .when(year.between(2018,2020),'train').when(year==2021,'validation').when(year==2022,'test').otherwise('excluded'))


def fit_preparation(df, columns, path=None, storage_backend='native'):
    """Fit and return Spark imputation, vector assembly and scaling on training rows."""
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import Imputer,VectorAssembler,StandardScaler
    training=df.filter("split = 'train'")
    if training.limit(1).count()==0:
        raise ValueError('No training rows; cannot fit preprocessing')
    for c in columns:
        if training.filter(F.col(c).isNotNull()).limit(1).count()==0:
            raise ValueError(f'All-null training feature: {c}')
    # Use new columns so raw values and missing-history evidence remain available.
    imputed=[c+'_imputed' for c in columns]
    model=Pipeline(stages=[Imputer(inputCols=columns,outputCols=imputed,strategy='median'),
                           VectorAssembler(inputCols=imputed,outputCol='unscaled_features'),
                           StandardScaler(inputCol='unscaled_features',outputCol='scaled_features',withMean=True,withStd=True)]).fit(training)
    if path is not None:
        from .storage import save_preparation
        save_preparation(model,path,backend=storage_backend)
    return model

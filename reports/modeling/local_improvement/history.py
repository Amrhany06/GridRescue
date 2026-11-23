"""Generate past-only history from the existing 20-county Silver partitions."""
import argparse
import json
import os
import shutil
import sys
import time

import psutil
from pyspark.sql import Window, functions as F

from thresholds import ARTIFACTS, BASE_DATA, BASE_REPORT, KEY, ROOT, metadata, write_json

sys.path.insert(0, str(ROOT / 'src'))
from gridrescue.modeling import FEATURE_COLUMNS
from gridrescue.pipeline import make_spark

ADDED = ['lag_120m', 'lag_180m', 'delta_180m', 'rolling_max_180m', 'reporting_coverage_180m',
         'trend_30m', 'relative_growth_180m', 'lag_120m_missing', 'lag_180m_missing',
         'trend_30m_missing', 'relative_growth_180m_missing']


def validate_silver(silver, allowed):
    """Reject invalid dates, off-grid observations, invalid counts and duplicate keys."""
    count = F.col('customers_out').cast('double')
    limits = (F.col('timestamp') >= F.lit('2018-01-01').cast('timestamp')) & (
        F.col('timestamp') < F.lit('2022-01-01').cast('timestamp'))
    valid = (F.col('fips_code').isin(allowed) & limits & (F.col('timestamp').cast('double') % 900 == 0)
             & (count >= 0) & ~F.isnan(count) & (count < float('inf')) & (F.floor(count) == count))
    if silver.filter(~F.coalesce(valid, F.lit(False))).limit(1).count():
        raise ValueError('Invalid Silver identifier, timestamp or outage count')
    if silver.groupBy(*KEY[:2]).count().where('count > 1').limit(1).count():
        raise ValueError('Duplicate Silver county and timestamp')


def history_features(silver):
    """Return a past-only feature row for each validated reporting anchor."""
    current = F.col('customers_out').cast('double')
    # Epoch seconds provide exact offsets even when reporting slots are absent.
    by_county = Window.partitionBy('fips_code').orderBy(F.unix_timestamp('timestamp'))
    lookback = by_county.rangeBetween(-10800, 0)
    augmented = silver.select(
        *KEY[:2], current.alias('_current'),
        F.max(current).over(by_county.rangeBetween(-1800, -1800)).alias('_lag_30m'),
        F.max(current).over(by_county.rangeBetween(-7200, -7200)).alias('lag_120m'),
        F.max(current).over(by_county.rangeBetween(-10800, -10800)).alias('lag_180m'),
        F.max(current).over(lookback).alias('rolling_max_180m'),
        (F.count(current).over(lookback) / F.lit(13.0)).alias('reporting_coverage_180m'),
    )
    # A missing exact lag propagates to the derived change. Zero is a valid report.
    augmented = augmented.withColumn('delta_180m', F.col('_current') - F.col('lag_180m'))
    augmented = augmented.withColumn('trend_30m', (F.col('_current') - F.col('_lag_30m')) / F.lit(30.0))
    augmented = augmented.withColumn('relative_growth_180m', F.when(
        F.col('lag_180m') > 0, F.col('delta_180m') / F.col('lag_180m')))
    for name in ('lag_120m', 'lag_180m', 'trend_30m', 'relative_growth_180m'):
        augmented = augmented.withColumn(f'{name}_missing', F.col(name).isNull().cast('byte'))
    return augmented.select(*KEY[:2], *ADDED)


def build_bucket(spark, counties, bucket, target):
    """Join new history to unchanged label keys and verify the native Parquet round trip."""
    silver = spark.read.parquet(str(BASE_DATA / 'silver' / f's{bucket}'))
    validate_silver(silver, counties.fips_code.tolist())
    seen = counties.loc[counties.role.eq('seen'), 'fips_code'].tolist()
    labels = spark.read.parquet(str(BASE_DATA / 'labels' / f's{bucket}'))
    # Drop held-out training anchors, while retaining their 2018–2020 reports as past history.
    eligible = (labels.where(F.col('candidate_y').isin(0, 1) & ((F.col('split') == 'validation') |
                ((F.col('split') == 'train') & F.col('fips_code').isin(seen))))
                .select(*KEY, 'split', 'state', 'future_slots', *FEATURE_COLUMNS))
    if eligible.where('future_slots != 12 OR future_slots IS NULL OR customers_out_t <= 0').limit(1).count():
        raise ValueError('Eligible labels violate the existing complete-horizon contract')
    expected = {(row.fips_code, row.split): row['count'] for row in eligible.groupBy('fips_code', 'split').count().collect()}
    joined = eligible.join(history_features(silver), KEY[:2], 'left')
    joined.repartition(2, 'split').write.mode('errorifexists').partitionBy('split').parquet(str(target))
    stored = spark.read.parquet(str(target))
    rows = stored.groupBy('fips_code', 'split').agg(
        F.count('*').alias('rows'), F.sum('candidate_y').alias('positives'),
        F.sum('lag_120m_missing').alias('lag_120m_missing'), F.sum('lag_180m_missing').alias('lag_180m_missing'),
        F.sum('relative_growth_180m_missing').alias('relative_growth_180m_missing'),
        F.avg('reporting_coverage_180m').alias('mean_coverage'),
        F.min('reporting_coverage_180m').alias('min_coverage'),
        F.max('reporting_coverage_180m').alias('max_coverage')).collect()
    if ({(row.fips_code, row.split): row.rows for row in rows} != expected
            or stored.where('reporting_coverage_180m IS NULL').limit(1).count()):
        raise ValueError('History join failed to preserve all eligible anchors')
    return [row.asDict() for row in rows]


def run(destination):
    """Process one state at a time with a 2 GiB Spark driver and ample free disk."""
    free_disk = shutil.disk_usage(ROOT).free
    available = psutil.virtual_memory().available
    if free_disk < 2 * 2**30 or available < 2.5 * 2**30:
        raise MemoryError(f'History needs 2 GiB free disk and 2.5 GiB available RAM; found {free_disk}, {available} bytes')
    cohort = metadata()
    audit = json.loads((BASE_REPORT / 'data_audit.json').read_text(encoding='utf-8'))
    destination.mkdir(parents=True)
    scratch = destination / 'spark_scratch'
    scratch.mkdir()
    os.environ['SPARK_LOCAL_DIRS'] = str(scratch)
    spark = make_spark('GridRescue local history')
    evidence = {'spark': spark.version,
                'hadoop': spark.sparkContext._jvm.org.apache.hadoop.util.VersionInfo.getVersion(),
                'free_disk_at_start': free_disk, 'available_ram_at_start': available, 'new_features': ADDED, 'states': {}}
    try:
        for bucket, counties in cohort.groupby(cohort.fips_code.str[:2]):
            started = time.perf_counter()
            result = build_bucket(spark, counties, bucket, destination / f's{bucket}')
            evidence['states'][bucket] = {
                'seconds': time.perf_counter() - started, 'rows': result,
                'available_ram_bytes': psutil.virtual_memory().available}
            print(f'{bucket}: wrote {sum(row["rows"] for row in result):,} matched anchors', flush=True)
        role = cohort.set_index('fips_code').role
        expected = {}
        for state in audit['state_audits']:
            for row in state['by_county_year_split']:
                code, split = row['fips_code'], row['split']
                if row['eligible'] and (split == 'validation' or (split == 'train' and role[code] == 'seen')):
                    key = code, split
                    previous = expected.get(key, (0, 0))
                    expected[key] = (previous[0] + row['eligible'], previous[1] + row['positive'])
        observed = {(row['fips_code'], row['split']): (row['rows'], row['positives'])
                    for state in evidence['states'].values() for row in state['rows']}
        if observed != expected:
            raise ValueError('History output disagrees with the verified expansion audit')
        write_json(destination / 'audit.json', evidence)
    finally:
        spark.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', default=ARTIFACTS / 'history', type=type(ROOT))
    run(parser.parse_args().destination)

"""Execute bounded real development sample. No model fitting; no 2022 access.

Run make_sample.py first. All metrics explicitly describe the prefix sample.
"""
import json
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.pipeline import make_spark,read_source,clean,features,audit_labels,fit_preparation,PREDICTORS
from gridrescue.storage import default_backend,scope_paths,write_frame,read_frame,load_preparation,compare_frame
from pyspark.sql import functions as F,Window


def records(df):
    # Spark's Python datetime conversion can use the host timezone on Windows.
    # Render timestamp fields inside Spark's explicitly UTC session first.
    for field in df.schema.fields:
        if field.dataType.typeName()=='timestamp':
            df=df.withColumn(field.name,F.date_format(F.col(field.name),'yyyy-MM-dd HH:mm:ss'))
    return [r.asDict(recursive=True) for r in df.collect()]


def save_json(path,value):
    path.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',choices=['sample','county'],default='sample')
    parser.add_argument('--audit-only',action='store_true',help='Compute in memory; do not claim Parquet or saved preparation verification')
    parser.add_argument('--storage',choices=['native','arrow-local'],default=default_backend())
    args=parser.parse_args()
    scope=args.scope
    locations=scope_paths(ROOT,scope,args.storage)
    report_dir=locations['report']
    if args.audit_only:
        report_dir=ROOT/'reports/memory'/scope
    report_dir.mkdir(parents=True,exist_ok=True)
    input_dir=ROOT/('data/sample' if scope=='sample' else 'data/county_coverage')
    spark=make_spark()
    out=locations['artifacts']; out.mkdir(parents=True,exist_ok=True)
    stage_paths={name:locations[name] for name in ['bronze','silver','quarantine','gold','label_audit']}
    report={'scope':('FIRST 100000 source rows per development year 2018-2021; NOT full population; 2022 untouched' if scope=='sample' else 'All source dates 2018-2021 for fixed counties 06037, 12086, 48201; geographic examples, not representative; 2022 untouched'),
            'utc':datetime.now(timezone.utc).isoformat(),'target_status':'APPROVED_CONDITIONAL_EXPERIMENT for fixed three counties; no predictive fitting in this preparation pipeline',
            'timestamp_policy':'Source naive timestamps interpreted as UTC per supplied project documentation; not inferred from strings'}
    report['storage_backend']='none' if args.audit_only else args.storage
    report['content_roundtrips']={}
    started=time.perf_counter()
    def persist(frame,path):
        if not args.audit_only:
            write_frame(frame,path,backend=args.storage)
            if args.storage=='arrow-local':
                report['content_roundtrips'][str(path.relative_to(ROOT)).replace('\\','/')]=compare_frame(frame,path)
    try:
        paths=sorted(input_dir.glob('*.csv'))
        if len(paths)!=4 or any('2022' in str(p) for p in paths):
            raise ValueError('Expected four development sample CSVs only')
        raw=read_source(spark,paths).cache()
        report['nulls_raw']=raw.select(*[F.sum(F.col(c).isNull().cast('long')).alias(c) for c in raw.columns]).first().asDict()
        report['unique_raw']=raw.select(*[F.countDistinct(c).alias(c) for c in raw.columns]).first().asDict()
        report['raw_exact_duplicate_rows']=raw.count()-raw.dropDuplicates(raw.columns).count()
        persist(raw,stage_paths['bronze'])
        if not args.audit_only:
            assert read_frame(spark,stage_paths['bronze']).count()==raw.count()
        silver,rejected,counts=clean(raw)
        report['counts']=counts
        persist(rejected,stage_paths['quarantine'])
        persist(silver,stage_paths['silver'])
        report['invalid_reasons']=records(rejected.groupBy('reason').count())
        report['year_counts']=records(silver.groupBy(F.year('timestamp').alias('year')).count().orderBy('year'))
        ordered=Window.partitionBy('fips_code',F.year('timestamp')).orderBy('timestamp')
        gaps=silver.withColumn('gap_seconds',F.unix_timestamp('timestamp')-F.unix_timestamp(F.lag('timestamp').over(ordered)))
        gap_summary=gaps.groupBy(F.year('timestamp').alias('year')).agg(F.sum(F.when(F.col('gap_seconds')>900,F.col('gap_seconds')/900-1).otherwise(0)).cast('long').alias('internal_missing_slots'),F.max('gap_seconds').alias('max_gap_seconds'))
        report['gaps']=records(gap_summary.orderBy('year'))
        persist(gap_summary,out/'gap_summary')
        report['gap_policy']='Within observed county-year min/max only; leading/trailing unknown periods excluded. No zero filling. Prefix extraction creates edge effects.'
        q=silver.approxQuantile('customers_out',[0.25,0.5,0.75,0.99],0.001)
        fence=q[2]+1.5*(q[2]-q[0])
        report['outliers']={'approx_quantiles_25_50_75_99':q,'relative_rank_error':0.001,'iqr_upper_fence':fence,'above_fence':silver.filter(F.col('customers_out')>fence).count(),'max':silver.agg(F.max('customers_out')).first()[0],'policy':'Retain all valid extreme counts; statistical rarity does not prove error. Log1p for display only; no learned capping.'}
        gold=features(silver).cache()
        assert gold.count()==counts['silver']
        persist(gold,stage_paths['gold'])
        labels=audit_labels(gold).cache()
        persist(labels,stage_paths['label_audit'])
        report['coverage_by_county_year']=records(labels.groupBy('fips_code','county','state',F.year('timestamp').alias('year')).agg(F.count('*').alias('observed_anchors'),F.countDistinct(F.to_date('timestamp')).alias('observed_days'),F.min('timestamp').alias('first'),F.max('timestamp').alias('last'),F.sum(F.col('candidate_y').isNotNull().cast('long')).alias('eligible'),F.sum((F.col('candidate_y')==1).cast('long')).alias('positive'),F.sum((F.col('candidate_y')==0).cast('long')).alias('negative')).orderBy('year','fips_code'))
        report['feature_missing_counts']=records(gold.agg(*[F.sum(F.col(c).isNull().cast('long')).alias(c) for c in PREDICTORS]))
        report['label_summary']=records(labels.groupBy(F.year('timestamp').alias('year'),'future_slots','candidate_y','split').count().orderBy('year','future_slots','candidate_y'))
        report['future_gap_summary']=records(labels.groupBy(F.year('timestamp').alias('year'),'label_complete').agg(F.max('future_max_gap_seconds').alias('largest_future_gap_seconds')))
        report['selection_bias']=records(labels.groupBy(F.year('timestamp').alias('year'),'state').agg(F.count('*').alias('all_anchors'),F.sum(F.col('candidate_y').isNotNull().cast('long')).alias('eligible_anchors'),F.avg('customers_out_t').alias('mean_current_all'),F.avg(F.when(F.col('candidate_y').isNotNull(),F.col('customers_out_t'))).alias('mean_current_eligible')))
        report['county_eligibility']=records(labels.groupBy(F.year('timestamp').alias('year'),'fips_code').agg(F.count('*').alias('anchors'),F.sum(F.col('candidate_y').isNotNull().cast('long')).alias('eligible')).groupBy('year').agg(F.count('*').alias('observed_counties'),F.sum((F.col('eligible')>0).cast('int')).alias('counties_with_eligible_anchors'),F.sum('eligible').alias('eligible_anchors')))
        report['splits']=records(labels.groupBy('split').agg(F.count('*').alias('all_anchors'),F.sum(F.col('candidate_y').isNotNull().cast('long')).alias('complete_candidate_anchors')))
        examples=[]
        for name,condition in [('positive','candidate_y = 1'),('negative','candidate_y = 0'),('incomplete','candidate_y IS NULL'),('boundary',"split = 'purged'")]:
            selected=labels.filter(condition).orderBy('timestamp','fips_code').limit(3)
            examples.extend([dict(example_type=name,**r) for r in records(selected.select('fips_code','timestamp','customers_out_t','escalation_threshold','future_slots','future_max','candidate_y','split'))])
        save_json(report_dir/'label_examples.json',examples)
        # Export actual future traces for independent hand checking.
        traces=[]
        for ex in examples:
            start=ex['timestamp']
            anchor_time=F.to_timestamp(F.lit(start))
            trace=silver.filter((F.col('fips_code')==ex['fips_code']) & (F.col('timestamp')>=anchor_time) & (F.col('timestamp')<=anchor_time+F.expr('INTERVAL 3 HOURS'))).orderBy('timestamp')
            traces.append({'anchor':ex,'trace':records(trace.select('timestamp','customers_out'))})
        save_json(report_dir/'label_traces.json',traces)
        eligible=labels.filter("candidate_y IS NOT NULL AND split IN ('train','validation')")
        columns=list(PREDICTORS)
        for c in ['lag_15m','lag_60m','delta_60m']:
            flag=c+'_missing'; eligible=eligible.withColumn(flag,F.col(c).isNull().cast('double')); columns.append(flag)
        report['preparation_features']=columns
        report['eligible_preparation_counts']=records(eligible.groupBy('split').count())
        if args.audit_only:
            report['preparation']='NOT FITTED OR SAVED in memory-only audit; Parquet verification remains blocked'
        elif eligible.filter("split='train'").limit(1).count():
            prep=fit_preparation(eligible,columns,out/'preparation',storage_backend=args.storage)
            report['preparation_statistics']={'feature_order':columns,'medians':prep.stages[0].surrogateDF.first().asDict(),
                'mean':list(prep.stages[-1].mean),'sample_std':list(prep.stages[-1].std),
                'training_rows':eligible.filter("split='train'").count(),'imputer_relative_error':prep.stages[0].getRelativeError()}
            prepared=prep.transform(eligible)
            write_frame(prepared,out/'prepared_features',backend=args.storage)
            if args.storage=='arrow-local':
                report['content_roundtrips']['prepared_features']=compare_frame(prepared,out/'prepared_features')
            # Reload is part of preparation verification (not model inference).
            reloaded=load_preparation(out/'preparation')
            assert reloaded.transform(eligible).count()==eligible.count()
            report['preparation']='VERIFIED train-only imputer/scaler; no predictive estimator; fixed three-county target conditionally approved'
        else:
            report['preparation']='BLOCKED no eligible training anchors'
        # Justified metadata join: observed source county -> state labels, not external predictors.
        metadata=silver.select('fips_code','county','state').distinct()
        ambiguous=metadata.groupBy('fips_code').count().filter('count > 1').select('fips_code')
        metadata=metadata.join(ambiguous,'fips_code','left_anti')
        joined=gold.drop('county','state').join(metadata,'fips_code','left')
        assert joined.count()==gold.count()
        report['metadata_join']={'purpose':'Reattach unique observed geography for dashboard display only; ambiguous geography withheld','before':gold.count(),'after':joined.count(),'ambiguous_counties':ambiguous.count()}
        daily=silver.groupBy('state','county',F.to_date('timestamp').alias('date')).agg(F.count('*').alias('observations'),F.avg('customers_out').alias('mean_customers_out'),F.max('customers_out').alias('peak_customers_out'),F.sum('customers_out').alias('sum_customer_observations'))
        # Sum is customer-observations, never unique people or outage events.
        daily.toPandas().to_csv(report_dir/'dashboard_daily.csv',index=False)
        def query(df):
            return df.filter(F.col('customers_out').cast('long')>=200).groupBy('state').agg(F.sum(F.col('customers_out').cast('long')).alias('total')).orderBy('state').collect()
        timings={}; results=[]
        spark.catalog.clearCache()
        # Both uncached reads; single ordered trial, OS cache not controlled.
        for fmt in ([] if args.audit_only else ['csv','parquet']):
            begin=time.perf_counter()
            df=read_source(spark,paths) if fmt=='csv' else read_frame(spark,stage_paths['bronze'])
            results.append(query(df)); timings[fmt+'_seconds']=time.perf_counter()-begin
        if args.audit_only:
            report['benchmark']='NOT RUN; memory-only audit does not verify Parquet'
        else:
            assert results[0]==results[1]
            report['benchmark']={**timings,'equal_results':True,'spark_cache_cleared_before_timing':True,'query':'customers_out>=200; group state; sum customers_out','caveat':'One trial CSV then Parquet; OS cache uncontrolled; sample only; no general speedup claim'}
        report['runtime_seconds']=time.perf_counter()-started
        report['execution']=('VERIFIED IN-MEMORY AUDIT ONLY; no storage/preparation verification: ' if args.audit_only else 'VERIFIED ')+scope+' development scope'
        save_json(report_dir/'audit.json',report)
        with (report_dir/'pipeline_log.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(report,default=str)+'\n')
        print(json.dumps(report,indent=2,default=str))
    except Exception as exc:
        report.update(execution='FAILED',error=repr(exc),runtime_seconds=time.perf_counter()-started)
        save_json(report_dir/'audit_failed.json',report)
        raise
    finally:
        spark.stop()


if __name__=='__main__':
    main()

"""Compare identical uncached/cached Spark queries on the bounded county CSVs."""
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.pipeline import make_spark,read_source
from pyspark.sql import functions as F


def main():
    spark=make_spark('GridRescue-query-benchmark')
    paths=[ROOT/'data/county_coverage'/f'eaglei_outages_{y}.csv' for y in range(2018,2022)]
    trials=[]
    expected=None
    rng=random.Random(17)
    try:
        for repetition in range(4):
            modes=['uncached_csv','cached_csv']
            rng.shuffle(modes)
            for mode in modes:
                spark.catalog.clearCache()
                frame=read_source(spark,paths)
                cache_build_seconds=0.0
                if mode=='cached_csv':
                    start=time.perf_counter()
                    frame=frame.cache()
                    assert frame.count()==418374
                    cache_build_seconds=time.perf_counter()-start
                query=(frame.filter(F.col('customers_out').cast('long')>=200).groupBy('state')
                       .agg(F.sum(F.col('customers_out').cast('long')).alias('sum_customer_observations')).orderBy('state'))
                start=time.perf_counter()
                result=[r.asDict() for r in query.collect()]
                elapsed=time.perf_counter()-start
                if expected is None:
                    expected=result
                assert result==expected
                plan=query._jdf.queryExecution().executedPlan().toString()
                assert ('InMemoryTableScan' in plan)==(mode=='cached_csv')
                if repetition>0:
                    trials.append({'repetition':repetition,'mode':mode,'query_seconds':elapsed,
                                   'cache_build_seconds':cache_build_seconds,'plan':plan})
        summary={mode:{'mean_query_seconds':statistics.mean(t['query_seconds'] for t in trials if t['mode']==mode),
                       'stdev_query_seconds':statistics.stdev(t['query_seconds'] for t in trials if t['mode']==mode),
                       'mean_cache_build_seconds':statistics.mean(t['cache_build_seconds'] for t in trials if t['mode']==mode)}
                 for mode in ['uncached_csv','cached_csv']}
        report={'status':'VERIFIED','completed_utc':datetime.now(timezone.utc).isoformat(),
                'scope':'418374 selected-county source records, 2018-2021; 2022 not opened',
                'query':'customers_out cast long >=200; group state; sum customer-observations; order state',
                'trials':trials,'summary':summary,'identical_results':expected,
                'method':'One warm-up pair excluded; three measured pairs in seeded randomized order; Spark cache cleared before every condition; query plans checked',
                'caveats':'Local[2], same process; JIT and OS filesystem caches uncontrolled. Cached query timing excludes separately reported cache construction. This is a repeated-query cache comparison, not CSV-versus-Parquet or a general cluster speedup.'}
        (ROOT/'reports/performance_comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(summary),flush=True)
    finally:
        spark.stop()


if __name__=='__main__':
    main()

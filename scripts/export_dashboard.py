"""Export verified FIPS-keyed daily history without changing prior results."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.pipeline import make_spark, read_source, clean
from pyspark.sql import functions as F


def main():
    spark=make_spark('GridRescue-dashboard-export')
    try:
        for scope,source_dir in [('sample','sample'),('county','county_coverage')]:
            audit_path=ROOT/'reports/memory'/scope/'audit.json'
            audit=json.loads(audit_path.read_text(encoding='utf-8'))
            paths=[ROOT/'data'/source_dir/f'eaglei_outages_{year}.csv' for year in range(2018,2022)]
            silver,_,counts=clean(read_source(spark,paths))
            assert counts==audit['counts']
            metadata=silver.select('fips_code','county','state').distinct()
            ambiguous=metadata.groupBy('fips_code').count().filter('count>1').select('fips_code')
            unique=metadata.join(ambiguous,'fips_code','left_anti')
            daily=(silver.groupBy('fips_code',F.to_date('timestamp').alias('date')).agg(
                F.count('*').alias('observations'),F.avg('customers_out').alias('mean_customers_out'),
                F.max('customers_out').alias('peak_customers_out'),F.sum('customers_out').alias('sum_customer_observations'))
                .join(unique,'fips_code','left').fillna({'county':'Geography withheld','state':'Unknown geography'}))
            frame=daily.orderBy('date','fips_code').toPandas()
            assert int(frame.observations.sum())==counts['silver']
            assert not frame.duplicated(['fips_code','date']).any()
            assert frame.observations.between(1,96).all()
            out=ROOT/'reports/dashboard'/scope
            out.mkdir(parents=True,exist_ok=True)
            path=out/'daily.csv'
            frame.to_csv(path,index=False)
            manifest={'status':'VERIFIED','scope':scope,'completed_utc':datetime.now(timezone.utc).isoformat(),
                      'source_audit':audit_path.relative_to(ROOT).as_posix(),'source_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                      'csv_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'observations':int(frame.observations.sum()),
                      'county_days':len(frame),'geography_withheld_fips':[r.fips_code for r in ambiguous.collect()],
                      'aggregation_key':['fips_code','date'],'2022_accessed':False}
            (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(manifest),flush=True)
            spark.catalog.clearCache()
    finally:
        spark.stop()


if __name__=='__main__':
    main()

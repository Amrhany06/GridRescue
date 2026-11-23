"""Bounded mismatch examples; full comparisons stay inside Spark."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.pipeline import make_spark,features
from gridrescue.storage import scope_paths,read_frame
from pyspark.sql import functions as F

spark=make_spark('GridRescue-storage-mismatch')
try:
    paths=scope_paths(ROOT,'county','arrow-local')
    left=features(read_frame(spark,paths['silver'])).cache()
    right=read_frame(spark,paths['gold']).cache()
    keys=['fips_code','epoch']
    joined=left.alias('a').join(right.alias('b'),keys,'full').cache()
    columns=[c for c in left.columns if c not in keys]
    counts=joined.agg(*[F.sum((~F.col('a.'+c).eqNullSafe(F.col('b.'+c))).cast('long')).alias(c) for c in columns]).first().asDict()
    examples={}
    for name,count in counts.items():
        if count:
            rows=joined.filter(~F.col('a.'+name).eqNullSafe(F.col('b.'+name))).select(*keys,F.col('a.'+name).cast('string').alias('original'),F.col('b.'+name).cast('string').alias('reloaded')).limit(8).collect()
            examples[name]=[row.asDict() for row in rows]
    report={'rows_original':left.count(),'rows_reloaded':right.count(),'schema_equal':left.schema==right.schema,'joined_rows':joined.count(),
            'mismatches_by_column':counts,'bounded_examples':examples,'2022_accessed':False}
    (ROOT/'reports/storage_mismatch_diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
finally:
    spark.stop()

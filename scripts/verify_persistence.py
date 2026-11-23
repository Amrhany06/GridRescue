"""Fresh-process reload of real processed datasets and fitted Spark preparation."""
import json
import sys
import argparse
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.pipeline import make_spark
from gridrescue.storage import default_backend,scope_paths,read_frame,load_preparation
from pyspark.sql import functions as F
from pyspark.ml import PipelineModel
from pyspark.ml.functions import vector_to_array


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage',choices=['native','arrow-local'],default=default_backend())
    args=parser.parse_args()
    spark=make_spark('GridRescue-persistence-reload')
    report={'status':'RUNNING','utc':datetime.now(timezone.utc).isoformat(),'scopes':{},'fresh_process':True,'2022_accessed':False,'storage_backend':args.storage}
    try:
        for scope in ['sample','county']:
            locations=scope_paths(ROOT,scope,args.storage)
            base=locations['artifacts']
            labels=read_frame(spark,locations['label_audit'])
            raw=labels.filter("candidate_y IS NOT NULL AND split IN ('train','validation')")
            for column in ['lag_15m','lag_60m','delta_60m']:
                raw=raw.withColumn(column+'_missing',F.col(column).isNull().cast('double'))
            model=load_preparation(base/'preparation')
            reloaded=model.transform(raw).select('fips_code','timestamp',vector_to_array('scaled_features').alias('reloaded'))
            saved=read_frame(spark,base/'prepared_features').select('fips_code','timestamp',vector_to_array('scaled_features').alias('saved'))
            compared=saved.join(reloaded,['fips_code','timestamp'],'inner').cache()
            total=compared.count()
            assert total==saved.count()==raw.count()
            mismatch=compared.filter(~F.col('saved').eqNullSafe(F.col('reloaded'))).count()
            invalid=compared.filter(F.exists('reloaded',lambda value:value.isNull()|F.isnan(value)|(F.abs(value)==F.lit(float('inf'))))).count()
            dimension_errors=compared.filter(F.size('reloaded')!=13).count()
            assert mismatch==0 and invalid==0 and dimension_errors==0
            stage_counts={name:read_frame(spark,locations[name]).count() for name in ['bronze','silver','quarantine','gold','label_audit']}
            audit=json.loads((locations['report']/'audit.json').read_text(encoding='utf-8'))
            fitted=audit['preparation_statistics']
            assert list(model.stages[-1].mean)==fitted['mean']
            assert list(model.stages[-1].std)==fitted['sample_std']
            assert model.stages[0].surrogateDF.first().asDict()==fitted['medians']
            assert list(model.stages[0].getInputCols())==list(model.stages[1].getInputCols()[i].removesuffix('_imputed') for i in range(13))==fitted['feature_order']
            missing_history=raw.filter('lag_15m IS NULL OR lag_60m IS NULL').count()
            assert missing_history>0
            assert stage_counts['bronze']==audit['counts']['raw']
            assert stage_counts['silver']==stage_counts['gold']==stage_counts['label_audit']==audit['counts']['silver']
            assert stage_counts['quarantine']==audit['counts']['invalid']+audit['counts']['conflict_rows']
            report['scopes'][scope]={'rows':total,'vector_dimension':13,'exact_vector_mismatches':mismatch,
                                    'nonfinite_vectors':invalid,'dimension_errors':dimension_errors,
                                    'persisted_stage_counts':stage_counts,
                                    'original_fitted_statistics_equal':True,'feature_order':fitted['feature_order'],
                                    'rows_exercising_missing_history':missing_history,
                                    'full_content_roundtrips':audit['content_roundtrips'],
                                    'stages':[type(stage).__name__ for stage in model.stages],
                                    'split_rows':{r['split']:r['count'] for r in raw.groupBy('split').count().collect()}}
            compared.unpersist()
        report['status']='VERIFIED'
        print(json.dumps(report,indent=2),flush=True)
    except Exception as error:
        report.update(status='FAILED',error=repr(error))
        raise
    finally:
        (ROOT/'reports/persistence_validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        spark.stop()


if __name__=='__main__':
    main()

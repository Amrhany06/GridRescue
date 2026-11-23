"""Reproduce native Windows I/O without changing the environment or raw data."""
import importlib.metadata
import json
import os
import platform
import sys
import traceback
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.pipeline import make_spark,fit_preparation

def main():
    destination=ROOT/'artifacts/windows_diagnosis'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    destination.mkdir(parents=True)
    report={'utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),
            'executable':sys.executable,'versions':{p:importlib.metadata.version(p) for p in ['pyspark','setuptools','pyarrow']},
            'environment':{k:os.environ.get(k) for k in ['JAVA_HOME','HADOOP_HOME','SPARK_HOME','PYSPARK_PYTHON','SPARK_LOCAL_IP']},
            'probes':{},'destination':destination.relative_to(ROOT).as_posix()}
    spark=make_spark('GridRescue-Windows-diagnosis')
    def probe(name,action):
        try:
            report['probes'][name]={'status':'PASS','output':action()}
        except Exception:
            report['probes'][name]={'status':'FAIL','exception':traceback.format_exc()}
        print(name,report['probes'][name]['status'],flush=True)
    try:
        jvm=spark._jvm
        report['java_runtime']=jvm.java.lang.System.getProperty('java.runtime.version')
        report['java_home']=jvm.java.lang.System.getProperty('java.home')
        report['hadoop_version']=jvm.org.apache.hadoop.util.VersionInfo.getVersion()
        report['native_hadoop_loaded']=jvm.org.apache.hadoop.util.NativeCodeLoader.isNativeCodeLoaded()
        report['hadoop_home_property']=jvm.java.lang.System.getProperty('hadoop.home.dir')
        report['filesystem_class']=jvm.org.apache.hadoop.fs.FileSystem.getLocal(spark.sparkContext._jsc.hadoopConfiguration()).getClass().getName()
        from pyspark.sql import functions as F
        frame=spark.range(20).withColumn('squared',F.col('id')*F.col('id')).filter('id%2=0')
        probe('spark_transformation',lambda:[r.asDict() for r in frame.groupBy().sum('squared').collect()])
        probe('winutils_lookup',lambda:jvm.org.apache.hadoop.util.Shell.getWinUtilsPath())
        def native_write():
            frame.write.mode('errorifexists').parquet(str(destination/'native.parquet'))
            return [r.asDict() for r in spark.read.parquet(str(destination/'native.parquet')).orderBy('id').collect()]
        probe('native_parquet',native_write)
        def arrow_then_spark():
            import pyarrow as pa,pyarrow.parquet as pq
            path=destination/'arrow.parquet'
            pq.write_table(pa.table({'id':[2,4],'squared':[4,16]}),path)
            return [r.asDict() for r in spark.read.parquet(str(path)).orderBy('id').collect()]
        probe('spark_reads_arrow_parquet',arrow_then_spark)
        def preparation_save():
            data=spark.createDataFrame([('train',1.),('train',3.),('validation',999.)],'split string,x double')
            model=fit_preparation(data,['x'])
            assert list(model.stages[-1].mean)==[2.]
            model.write().save(str(destination/'native_preparation'))
            return 'saved'
        probe('native_preparation_save',preparation_save)
        report['2022_accessed']=False
    finally:
        spark.stop()
        (ROOT/'reports/windows_spark_probes.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()

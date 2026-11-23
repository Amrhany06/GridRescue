"""Explicit local persistence adapter; Spark remains the computation engine.

Windows: stream Spark rows into PyArrow Parquet, then read them with Spark.
The JSON preparation format restores genuine Spark 3.5.3 ML stages from their
fitted statistics; it never refits, downloads code, or invokes pickle.
Native Hadoop writing remains available on Linux or by explicit selection.
"""
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime,timezone
from pathlib import Path

from pyspark.sql import SparkSession,functions as F
from pyspark.sql.types import StructType,StructField,TimestampType,LongType
from pyspark.ml.linalg import VectorUDT,Vectors
from pyspark.ml.functions import vector_to_array,array_to_vector

MANIFEST='_gridrescue_storage.json'

def default_backend():
    return 'arrow-local' if os.name=='nt' else 'native'

def scope_paths(root,scope,backend=None):
    root=Path(root); backend=backend or default_backend()
    data=root/('data/windows' if backend=='arrow-local' else 'data')
    artifacts=root/('artifacts/windows' if backend=='arrow-local' else 'artifacts')/scope
    report=root/'reports/windows'/scope if backend=='arrow-local' else root/'reports' if scope=='sample' else root/'reports/county'
    return {'bronze':data/'bronze'/scope,'silver':data/'silver'/scope,
            'quarantine':data/'silver'/(scope+'_quarantine'),'gold':data/'gold'/scope/'features',
            'label_audit':data/'gold'/scope/'label_audit','artifacts':artifacts,'report':report}

def sha256(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def _commit(staging,target):
    """Retain prior working/partial output instead of deleting it on rerun."""
    def rename(source,destination):
        for attempt in range(5):
            try:
                source.rename(destination)
                return
            except PermissionError:
                if attempt==4: raise
                time.sleep(.1*(2**attempt))
    history=None
    if target.exists():
        history=target.with_name(target.name+'.previous-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
        rename(target,history)
    try:
        rename(staging,target)
    except Exception:
        if history is not None and not target.exists():
            rename(history,target)
        raise

def write_frame(frame,path,backend=None,batch_rows=8192,max_rows=500000):
    backend=backend or default_backend()
    if backend=='native':
        frame.write.mode('overwrite').parquet(str(path)); return
    if backend!='arrow-local' or not 1<=batch_rows<=8192 or not 1<=max_rows<=500000:
        raise ValueError('Invalid persistence backend/batch size/row budget')
    if frame.limit(max_rows+1).count()>max_rows:
        raise ValueError(f'Arrow-local row budget exceeded ({max_rows:,}); use the native Linux backend for larger datasets')
    import pyarrow as pa,pyarrow.parquet as pq
    from pyspark.sql.pandas.types import to_arrow_schema
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=target.name+'.writing-',dir=target.parent))
    physical=frame
    vectors=[field.name for field in frame.schema if isinstance(field.dataType,VectorUDT)]
    for name in vectors: physical=physical.withColumn(name,vector_to_array(name))
    arrow_schema=to_arrow_schema(physical.schema)
    # PySpark's Python datetime conversion uses the host timezone. Transfer UTC
    # epoch microseconds instead; Arrow writes adjusted-to-UTC timestamps.
    for field in physical.schema:
        if isinstance(field.dataType,TimestampType): physical=physical.withColumn(field.name,F.unix_micros(field.name))
    # Round-robin redistribution bounds the iterator's largest partition for
    # this explicitly capped local cohort. It does not collect the whole frame.
    physical=physical.repartition(8).withColumn('__gridrescue_export_partition',F.spark_partition_id())
    writer=pq.ParquetWriter(staging/'part-00000.parquet',arrow_schema,compression='snappy')
    import psutil
    process=psutil.Process()
    initial_rss=process.memory_info().rss; sampled_peak_rss=initial_rss
    rows=[]; total=0; partition_rows={}
    try:
        for row in physical.toLocalIterator(prefetchPartitions=False):
            values=row.asDict(recursive=True)
            partition=values.pop('__gridrescue_export_partition')
            partition_rows[partition]=partition_rows.get(partition,0)+1
            rows.append(values)
            if len(rows)>=batch_rows:
                writer.write_table(pa.Table.from_pylist(rows,schema=arrow_schema)); total+=len(rows); rows=[]
                sampled_peak_rss=max(sampled_peak_rss,process.memory_info().rss)
        if rows:
            writer.write_table(pa.Table.from_pylist(rows,schema=arrow_schema)); total+=len(rows)
            sampled_peak_rss=max(sampled_peak_rss,process.memory_info().rss)
    finally:
        writer.close()
    part=staging/'part-00000.parquet'
    metadata={'format':'gridrescue-arrow-local-v1','rows':total,'spark_schema':frame.schema.jsonValue(),
              'vector_columns':vectors,'timestamp_policy':'UTC epoch microseconds; Arrow adjusted-to-UTC',
              'parts':[{'name':part.name,'sha256':sha256(part)}],
              'io_only':'Spark computed all rows; PyArrow performed local encoding only',
              'memory_policy':'Capped local cohort, eight round-robin Spark export partitions, bounded Arrow batches; iterator buffers up to the largest partition',
              'row_budget':max_rows,'arrow_batch_rows':batch_rows,'partition_rows':partition_rows,
              'python_rss_initial_bytes':initial_rss,'python_rss_sampled_peak_bytes':sampled_peak_rss,
              'memory_measurement_limit':'RSS sampled at batch boundaries; excludes JVM and does not establish absolute peak',
              'largest_export_partition_rows':max(partition_rows.values(),default=0),
              'spark_partitions':physical.rdd.getNumPartitions()}
    (staging/MANIFEST).write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    _commit(staging,target)

def read_frame(spark,path):
    path=Path(path)
    if not (path/MANIFEST).exists(): return spark.read.parquet(str(path))
    metadata=json.loads((path/MANIFEST).read_text(encoding='utf-8'))
    if metadata.get('format')!='gridrescue-arrow-local-v1': raise ValueError('Unknown Parquet manifest format')
    parts=[]
    for part in metadata['parts']:
        filename=path/part['name']
        if filename.parent.resolve()!=path.resolve() or sha256(filename)!=part['sha256']: raise ValueError('Parquet hash mismatch')
        parts.append(str(filename))
    frame=spark.read.parquet(*parts)
    schema=StructType.fromJson(metadata['spark_schema'])
    for name in metadata['vector_columns']:
        frame=frame.withColumn(name,array_to_vector(name).alias(name,metadata=schema[name].metadata))
    frame=frame.select(*schema.fieldNames())
    # Parquet readers relax nullability and omit some Spark ML metadata. Restore
    # the exact saved schema through a distributed, row-streamed Spark RDD;
    # no driver collect/toPandas is involved, and values are not altered.
    if frame.schema!=schema:
        bridge_fields=[]
        for field in schema:
            if isinstance(field.dataType,TimestampType):
                frame=frame.withColumn(field.name,F.unix_micros(field.name))
                bridge_fields.append(StructField(field.name,LongType(),field.nullable,field.metadata))
            else:
                bridge_fields.append(field)
        # Never pass a naive datetime through the host's ambiguous local clock.
        frame=spark.createDataFrame(frame.rdd,schema=StructType(bridge_fields),verifySchema=True)
        for field in schema:
            if isinstance(field.dataType,TimestampType):
                frame=frame.withColumn(field.name,F.timestamp_micros(field.name).alias(field.name,metadata=field.metadata))
    return frame

def compare_frame(original,path):
    """Compare every row/value in Spark; collect only one compact summary."""
    loaded=read_frame(original.sparkSession,path)
    schema_equal=original.schema==loaded.schema
    assert schema_equal,'Persisted Spark schema differs'
    left,right=original,loaded
    for field in original.schema:
        if isinstance(field.dataType,VectorUDT):
            left=left.withColumn(field.name,vector_to_array(field.name))
            right=right.withColumn(field.name,vector_to_array(field.name))
    missing=left.exceptAll(right).count(); extra=right.exceptAll(left).count()
    assert missing==extra==0,'Persisted values differ'
    summaries=[]
    for frame in [left,right]:
        summaries.append(frame.agg(F.count('*').alias('__rows'),*[F.sum(F.col(c).isNull().cast('long')).alias(c) for c in frame.columns]).first().asDict())
    assert summaries[0]==summaries[1]
    return {'schema_equal_including_nullability_and_metadata':schema_equal,'feature_and_column_order_equal':original.columns==loaded.columns,
            'rows':summaries[0].pop('__rows'),'source_null_counts':summaries[0],
            'missing_or_changed_rows':missing,'extra_or_changed_rows':extra,
            'numeric_and_timestamp_comparison':'Exact Spark exceptAll multiset equality across every column'}

def save_preparation(model,path,backend=None):
    backend=backend or default_backend()
    if backend=='native': model.write().overwrite().save(str(path)); return
    if backend!='arrow-local': raise ValueError('Unknown preparation backend')
    from pyspark.ml.feature import ImputerModel,VectorAssembler,StandardScalerModel
    imputer,assembler,scaler=model.stages
    if not isinstance(imputer,ImputerModel) or not isinstance(assembler,VectorAssembler) or not isinstance(scaler,StandardScalerModel):
        raise ValueError('Only the existing three-stage preparation is supported')
    if imputer.getStrategy()!='median' or not __import__('math').isnan(imputer.getMissingValue()):
        raise ValueError('Unexpected imputation policy')
    metadata={'format':'gridrescue-spark-preparation-v1','spark_version':SparkSession.getActiveSession().version,
        'pipeline_uid':model.uid,'imputer':{'uid':imputer.uid,'input_cols':imputer.getInputCols(),
            'output_cols':imputer.getOutputCols(),'medians':imputer.surrogateDF.first().asDict(),
            'relative_error':imputer.getRelativeError(),'strategy':'median','missing_value':'NaN'},
        'assembler':{'uid':assembler.uid,'input_cols':assembler.getInputCols(),'output_col':assembler.getOutputCol(),
                     'handle_invalid':assembler.getHandleInvalid()},
        'scaler':{'uid':scaler.uid,'input_col':scaler.getInputCol(),'output_col':scaler.getOutputCol(),
                  'with_mean':scaler.getWithMean(),'with_std':scaler.getWithStd(),
                  'mean':list(scaler.mean),'std':list(scaler.std)},'refit_on_reload':False}
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=target.name+'.writing-',dir=target.parent))
    (staging/'preparation.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    _commit(staging,target)

def load_preparation(path):
    from pyspark.ml import PipelineModel
    from pyspark.ml.feature import ImputerModel,VectorAssembler,StandardScalerModel
    from pyspark.ml.wrapper import JavaWrapper
    path=Path(path)
    if not (path/'preparation.json').exists(): return PipelineModel.load(str(path))
    metadata=json.loads((path/'preparation.json').read_text(encoding='utf-8'))
    spark=SparkSession.getActiveSession()
    if metadata.get('format')!='gridrescue-spark-preparation-v1': raise ValueError('Unknown preparation format')
    if metadata['spark_version']!='3.5.3' or spark.version!=metadata['spark_version']:
        raise ValueError('Spark version must match the verified 3.5.3 reconstruction API')
    imp,assembly,scale=metadata['imputer'],metadata['assembler'],metadata['scaler']
    if imp['strategy']!='median' or imp['missing_value']!='NaN': raise ValueError('Unexpected imputation policy')
    columns=imp['input_cols']
    surrogate=spark.createDataFrame([tuple(float(imp['medians'][c]) for c in columns)],', '.join('`'+c+'` double' for c in columns))
    # Spark constructors are version-specific, explicitly pinned and tested.
    imputer=ImputerModel(JavaWrapper._new_java_obj('org.apache.spark.ml.feature.ImputerModel',imp['uid'],surrogate._jdf))
    imputer._set(inputCols=columns,outputCols=imp['output_cols'],strategy='median',missingValue=float('nan'),relativeError=imp['relative_error'])
    assembler=VectorAssembler(inputCols=assembly['input_cols'],outputCol=assembly['output_col'],handleInvalid=assembly['handle_invalid'])
    assembler._resetUid(assembly['uid'])
    scaler=StandardScalerModel(JavaWrapper._new_java_obj('org.apache.spark.ml.feature.StandardScalerModel',scale['uid'],Vectors.dense(scale['std']),Vectors.dense(scale['mean'])))
    scaler._set(inputCol=scale['input_col'],outputCol=scale['output_col'],withMean=scale['with_mean'],withStd=scale['with_std'])
    model=PipelineModel([imputer,assembler,scaler]); model._resetUid(metadata['pipeline_uid'])
    return model

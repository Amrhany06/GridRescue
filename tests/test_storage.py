"""Portable persistence must preserve Spark values and fitted preprocessing."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from pyspark.sql import functions as F
from pyspark.ml.functions import vector_to_array
from gridrescue.pipeline import make_spark,fit_preparation
from gridrescue.storage import write_frame,read_frame,save_preparation,load_preparation
from gridrescue.storage import _commit
from unittest.mock import patch


class FileCommitTests(unittest.TestCase):
    def test_commit_retries_transient_windows_rename_denial_without_changing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory); staging=parent/'writing'; target=parent/'saved'
            staging.mkdir(); (staging/'content').write_bytes(b'exact original bytes')
            original=Path.rename; attempts=[]
            def transient(source,destination):
                if source==staging and len(attempts)<2:
                    attempts.append(1); raise PermissionError('temporary Windows sharing denial')
                return original(source,destination)
            with patch.object(Path,'rename',transient): _commit(staging,target)
            self.assertEqual((target/'content').read_bytes(),b'exact original bytes')
            self.assertEqual(len(attempts),2)

    def test_commit_permanent_failure_preserves_previous_working_output(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory); staging=parent/'writing'; target=parent/'saved'
            staging.mkdir(); target.mkdir(); (target/'content').write_bytes(b'previous verified output')
            original=Path.rename
            def permanent(source,destination):
                if source==staging: raise PermissionError('permanent sharing denial')
                return original(source,destination)
            with patch.object(Path,'rename',permanent):
                with self.assertRaises(PermissionError): _commit(staging,target)
            self.assertEqual((target/'content').read_bytes(),b'previous verified output')


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.spark=make_spark('GridRescue-storage-tests')
    @classmethod
    def tearDownClass(cls): cls.spark.stop()

    def test_parquet_preserves_timestamps_nulls_ids_and_transformed_content(self):
        frame=self.spark.createDataFrame([('01001','2020-06-01 23:45:00',2.),('01003','2020-06-02 00:00:00',None)],'fips_code string,t string,x double').withColumn('timestamp',F.to_timestamp('t')).drop('t').withColumn('square',F.col('x')**2)
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'rows'
            write_frame(frame,target,backend='arrow-local',batch_rows=1)
            loaded=read_frame(self.spark,target)
            self.assertEqual(frame.exceptAll(loaded.select(*frame.columns)).count(),0)
            self.assertEqual(loaded.select(*frame.columns).exceptAll(frame).count(),0)
            self.assertEqual(frame.schema,loaded.schema)
            part=next(target.glob('*.parquet')); part.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'hash mismatch'): read_frame(self.spark,target)

    def test_schema_metadata_and_nullability_are_preserved(self):
        frame=self.spark.range(3).withColumn('label',F.lit('county')).withColumn('id',F.col('id').alias('id',metadata={'meaning':'synthetic key'}))
        with tempfile.TemporaryDirectory() as directory:
            write_frame(frame,Path(directory)/'rows',backend='arrow-local')
            self.assertEqual(read_frame(self.spark,Path(directory)/'rows').schema,frame.schema)

    def test_schema_restore_preserves_utc_at_ambiguous_windows_local_times(self):
        # Actual county verification exposed 48 one-hour shifts at these
        # historical Windows-local clock transitions. These are synthetic rows.
        frame=self.spark.range(4).withColumn('timestamp',F.to_timestamp(F.when(F.col('id')==0,'2018-10-25 20:00:00').when(F.col('id')==1,'2019-10-31 20:30:00').when(F.col('id')==2,'2020-10-29 20:45:00').otherwise('2021-10-28 20:00:00')))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rows'
            write_frame(frame,path,backend='arrow-local')
            restored=read_frame(self.spark,path)
            self.assertEqual(restored.schema,frame.schema)
            expected=frame.select('id',F.unix_micros('timestamp').alias('epoch_us'))
            actual=restored.select('id',F.unix_micros('timestamp').alias('epoch_us'))
            self.assertEqual(expected.exceptAll(actual).count(),0)
            self.assertEqual(actual.exceptAll(expected).count(),0)

    def test_export_refuses_inputs_beyond_explicit_local_row_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'row budget'):
                write_frame(self.spark.range(3),Path(directory)/'rows',backend='arrow-local',max_rows=2)
            self.assertFalse((Path(directory)/'rows').exists())

    def test_fitted_parameters_reload_without_refitting_and_vectors_match(self):
        frame=self.spark.createDataFrame([('train',1.,0.),('train',3.,0.),('train',None,0.),('validation',999.,5.)],'split string,x double,constant double')
        model=fit_preparation(frame,['x','constant'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'preparation'
            save_preparation(model,path,backend='arrow-local')
            loaded=load_preparation(path)
            self.assertEqual(list(loaded.stages[-1].mean),list(model.stages[-1].mean))
            self.assertEqual(list(loaded.stages[-1].std),list(model.stages[-1].std))
            self.assertEqual(loaded.stages[0].surrogateDF.first(),model.stages[0].surrogateDF.first())
            expected=model.transform(frame).select('split','x',vector_to_array('scaled_features').alias('v'))
            actual=loaded.transform(frame).select('split','x',vector_to_array('scaled_features').alias('v'))
            self.assertEqual(expected.exceptAll(actual).count(),0)
            self.assertEqual(actual.exceptAll(expected).count(),0)
            write_frame(model.transform(frame),Path(directory)/'vectors',backend='arrow-local')
            restored=read_frame(self.spark,Path(directory)/'vectors')
            persisted_vectors=restored.select('split','x',vector_to_array('scaled_features').alias('v'))
            # DataFrame row order is undefined. Preserve key/value association,
            # multiplicities and exact vector entries in BOTH directions.
            self.assertEqual(persisted_vectors.exceptAll(expected).count(),0)
            self.assertEqual(expected.exceptAll(persisted_vectors).count(),0)
            metadata=json.loads((path/'preparation.json').read_text())
            metadata['spark_version']='0.0.0'
            (path/'preparation.json').write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError,'Spark version'): load_preparation(path)

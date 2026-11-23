"""Verify native Spark storage on synthetic fixtures and optionally check development artifacts."""
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def native_storage(spark, scratch, report):
    """Exercise the native Hadoop committer and Spark ML writer in a disposable directory."""
    from pyspark.ml import PipelineModel
    from gridrescue.pipeline import fit_preparation

    hadoop = spark._jvm.org.apache.hadoop
    report['spark_version'] = spark.version
    report['hadoop_version'] = hadoop.util.VersionInfo.getVersion()
    report['hadoop_native_library_loaded'] = hadoop.util.NativeCodeLoader.isNativeCodeLoaded()
    if os.name == 'nt' and report['hadoop_native_library_loaded']:
        report['winutils'] = str(hadoop.util.Shell.getWinUtilsFile())
        report['hadoop_dll'] = str(hadoop.util.NativeCodeLoader.getLibraryName())
        assert hadoop.io.nativeio.NativeIO.isAvailable(), 'Windows Hadoop NativeIO did not initialize'

    assert spark.createDataFrame([(1,)], 'x int').first().x == 1
    report['spark_python_worker'] = 'VERIFIED'
    path = str(scratch / 'parquet')
    spark.range(5).write.parquet(path)
    assert [row.id for row in spark.read.parquet(path).orderBy('id').collect()] == list(range(5))

    # Use nullable fields for exact schema comparison through a Parquet reader.
    fixture = spark.createDataFrame([(0, 'train', 1.0), (1, 'train', 3.0), (2, 'validation', None)],
                                    'id long, split string, x double')
    fixture.write.mode('overwrite').parquet(path)
    restored = spark.read.parquet(path)
    assert restored.schema == fixture.schema
    assert restored.orderBy('id').collect() == fixture.orderBy('id').collect()
    report['spark_parquet'] = 'VERIFIED'
    report['parquet_fixture'] = {'initial_rows': 5, 'overwrite_rows': 3, 'schema_exact': True}

    model_path = str(scratch / 'preparation')
    fitted = fit_preparation(fixture, ['x'], path=model_path, storage_backend='native')
    loaded = PipelineModel.load(model_path)
    assert list(fitted.stages[-1].mean) == list(loaded.stages[-1].mean) == [2.0]
    expected = fitted.transform(fixture).select('id', 'scaled_features').orderBy('id').collect()
    actual = loaded.transform(fixture).select('id', 'scaled_features').orderBy('id').collect()
    assert actual == expected
    report['spark_pipeline_save_reload'] = 'VERIFIED'


def development_fixtures(spark, scratch):
    """Dry-run the evaluator's write paths and verify the saved development artifacts."""
    from datetime import timedelta
    import numpy as np
    import pandas as pd
    from gridrescue.experiment import digest, fingerprint
    from gridrescue.inference import METADATA, load_frozen_pipeline, predict_escalation
    from gridrescue.modeling import FEATURE_COLUMNS
    from gridrescue.pipeline import SOURCE, audit_labels, clean, features
    from gridrescue.storage import load_preparation, scope_paths

    metadata = json.loads((ROOT / METADATA).read_text(encoding='utf-8'))
    assert metadata['selection']['fingerprint'] == fingerprint(ROOT)[0]
    fixture_path = ROOT / metadata['reload_sample']
    assert digest(fixture_path) == metadata['reload_sample_sha256']
    fixture = pd.read_parquet(fixture_path)
    assert fixture.columns.tolist() == [*FEATURE_COLUMNS, 'expected_prediction', 'expected_score']
    scores = predict_escalation(load_frozen_pipeline(ROOT, metadata), fixture[FEATURE_COLUMNS])
    np.testing.assert_array_equal(scores.prediction, fixture.expected_prediction)
    np.testing.assert_array_equal(scores.score, fixture.expected_score)

    proof = json.loads((ROOT / 'reports/persistence_validation.json').read_text(encoding='utf-8'))
    county = scope_paths(ROOT, 'county', proof['storage_backend'])
    preparation = load_preparation(county['artifacts'] / 'preparation')
    assert preparation.stages[0].getInputCols() == FEATURE_COLUMNS

    # Cover complete windows and quarantine writes using generated 2020 reports.
    start = datetime(2020, 6, 1, 12)
    records = [('06037', 'Fixture', 'CA', str(400 if index == 5 else 100),
                (start + timedelta(minutes=15 * index)).strftime('%Y-%m-%d %H:%M:%S'))
               for index in range(15)]
    records.append(('06037', 'Fixture', 'CA', 'invalid', '2020-06-01 16:00:00'))
    silver, quarantine, _ = clean(spark.createDataFrame(records, ', '.join(f'{name} string' for name in SOURCE)))
    labels = audit_labels(features(silver))
    assert labels.filter("candidate_y IS NOT NULL AND split = 'train'").count() == 3
    for name, frame, rows in [('label_audit', labels, 15), ('quarantine', quarantine, 1)]:
        path = str(scratch / name)
        frame.write.mode('errorifexists').parquet(path)
        readback = spark.read.parquet(path)
        # Native Parquet reads every field as nullable. Names, types and values must match.
        assert readback.dtypes == frame.dtypes and readback.count() == rows
        assert readback.exceptAll(frame).count() == frame.exceptAll(readback).count() == 0
    return {'status': 'VERIFIED', 'frozen_model_fixture_rows': len(fixture), 'exact_scores': True,
            'feature_dimension': len(FEATURE_COLUMNS), 'synthetic_label_audit_rows': 15,
            'synthetic_quarantine_rows': 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development-fixtures', action='store_true',
                        help='Also verify frozen model and evaluator writes on development-only fixtures.')
    args = parser.parse_args()
    report={'utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'executable':sys.executable,
            'platform':platform.platform(),'java_home':os.environ.get('JAVA_HOME'),
            'hadoop_home':os.environ.get('HADOOP_HOME'),
            'java':subprocess.run(['java','-version'],capture_output=True,text=True).stderr,
            'versions':{}, 'status':'BLOCKED'}
    for package in ['pyspark','pandas','nbformat','nbclient','scikit-learn','streamlit']:
        try:
            report['versions'][package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report['versions'][package]='MISSING'
    try:
        from gridrescue.pipeline import make_spark
        workspace = ROOT / 'artifacts'
        workspace.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='native-spark-preflight-', dir=workspace) as directory:
            spark = make_spark('GridRescue-preflight')
            try:
                native_storage(spark, Path(directory), report)
                if args.development_fixtures:
                    report['development_fixtures'] = development_fixtures(spark, Path(directory))
            finally:
                spark.stop()
        report.update(status='VERIFIED', scratch_cleaned=True)
    except Exception:
        report.setdefault('spark_parquet', 'BLOCKED')
        report['error']=traceback.format_exc()
    (ROOT/'reports').mkdir(exist_ok=True)
    path=ROOT/'reports/environment.json'
    history=ROOT/'reports/environment_log.jsonl'
    if path.exists() and not history.exists():
        with history.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(json.loads(path.read_text(encoding='utf-8')))+'\n')
    with history.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(report)+'\n')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='VERIFIED' else 1


if __name__=='__main__':
    raise SystemExit(main())

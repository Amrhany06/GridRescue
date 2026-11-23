"""Once-only held-out evaluation, after frozen development selection.

Notebook reruns replay saved evidence. They never silently reopen the test CSV.
"""
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .experiment import (approved, add_missing_flags, digest, fingerprint, fit,
                         load_development, probability, progress, write_json)
from .modeling import (FEATURE_COLUMNS, claim_final_evaluation,
                       classification_metrics, make_model)


def completed_result(root, selection):
    """Refuse any second test access, including after interruption or tampering."""
    root = Path(root)
    journal_path = root/'reports/modeling/final_evaluation_journal.json'
    if not journal_path.exists():
        return None
    journal = json.loads(journal_path.read_text(encoding='utf-8'))
    if journal.get('status') != 'COMPLETE':
        raise RuntimeError('Final-test access already started but did not complete; explicit recovery approval is required.')
    result_path = root/'reports/modeling/final_evaluation.json'
    if digest(result_path) != journal['result_sha256']:
        raise RuntimeError('Final result changed after evaluation')
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if result['selection'] != selection:
        raise RuntimeError('Frozen selection changed after final evaluation')
    for name in ['artifact','predictions','reload_sample']:
        if digest(root/result[name]) != result[name+'_sha256']:
            raise RuntimeError(f'Final {name} hash mismatch')
    return result


def extract_test(source, destination, counties):
    # This function is called only after the exclusive journal is on disk.
    from .pipeline import SOURCE
    parsed = selected = 0
    with source.open(newline='', encoding='utf-8-sig') as src, destination.open('w', newline='', encoding='utf-8') as dst:
        reader, writer = csv.reader(src), csv.writer(dst)
        if next(reader) != SOURCE:
            raise ValueError('Unexpected final-source header')
        writer.writerow(SOURCE)
        for row in reader:
            if len(row) != len(SOURCE):
                raise ValueError(f'Invalid source record {parsed+1}')
            parsed += 1
            if row[0] in counties:
                selected += 1
                writer.writerow(row)
    return {'parsed_source_records': parsed, 'selected_raw_records': selected}


def run_final(root):
    root = Path(root).resolve()
    approval = approved(root)
    selection_path = root/'reports/modeling/frozen_selection.json'
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    previous = completed_result(root, selection)
    if previous is not None:
        return previous
    run_hash, _ = fingerprint(root)
    development = json.loads((root/'reports/modeling/development.json').read_text(encoding='utf-8'))
    if development['status'] != 'VERIFIED_DEVELOPMENT' or run_hash != selection['fingerprint'] or not selection['frozen']:
        raise RuntimeError('Development evidence and frozen selection must match before final evaluation')
    frame = load_development(root)
    final_pipeline = make_model(selection['model'], selection['parameters'])
    progress(root, 'final_refit', {'model': selection['model'], 'development_rows': len(frame)})
    seconds, messages = fit(final_pipeline, frame[FEATURE_COLUMNS], frame.candidate_y)
    artifact = root/'artifacts/modeling/selected_pipeline.joblib'
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_pipeline, artifact, compress=3)
    # All development choices and final refit precede the first held-out read.
    journal_path = root/'reports/modeling/final_evaluation_journal.json'
    claim_final_evaluation(journal_path, selection)
    spark = None
    try:
        source = root/'data/raw/eaglei_outages_2022.csv'
        inventory = json.loads((root/'reports/source_manifest.json').read_text(encoding='utf-8'))
        expected = next(item for item in inventory['files'] if item['path'] == 'data/raw/eaglei_outages_2022.csv')
        source_sha = digest(source)
        if source_sha != expected['sha256']:
            raise ValueError('Held-out source differs from original inventory')
        directory = root/'data/final_test'
        directory.mkdir(exist_ok=True)
        extracted = directory/source.name
        extraction = extract_test(source, extracted, set(approval['county_fips']))
        assert extraction['parsed_source_records'] == expected['row_count']
        from .pipeline import make_spark, read_source, clean, features, audit_labels
        from pyspark.sql import functions as F
        spark = make_spark('GridRescue-once-only-final-test')
        silver, quarantine, counts = clean(read_source(spark, [extracted]))
        assert not silver.filter(F.year('timestamp') != 2022).limit(1).count()
        labels = audit_labels(features(silver)).cache()
        labels.write.mode('errorifexists').parquet(str(directory/'label_audit'))
        quarantine.write.mode('errorifexists').parquet(str(directory/'quarantine'))
        coverage = [{'fips_code': row['fips_code'], 'observed': row['count'],
                     'nominal_quarter_hours': 365*96, 'coverage': row['count']/(365*96)}
                    for row in silver.groupBy('fips_code').count().collect()]
        if set(row['fips_code'] for row in coverage) != set(approval['county_fips']) or any(row['coverage'] < .9 for row in coverage):
            raise RuntimeError('Final county coverage failed the predeclared 90% qualification; no population substitution allowed')
        cohort = labels.filter("candidate_y IS NOT NULL AND split = 'test'")
        test = cohort.select('fips_code','timestamp','candidate_y','future_slots',*FEATURE_COLUMNS[:10]).toPandas()
        test['timestamp'] = pd.to_datetime(test.timestamp, utc=True)
        test = add_missing_flags(test).sort_values(['timestamp','fips_code']).reset_index(drop=True)
        for column in FEATURE_COLUMNS:
            test[column] = pd.to_numeric(test[column], errors='raise').astype(float)
        test['candidate_y'] = test.candidate_y.astype(int)
        assert (test.future_slots == 12).all() and (test.customers_out_t > 0).all()
        assert (test.timestamp.dt.year == 2022).all()
        assert not test.duplicated(['fips_code','timestamp']).any()
        assert not np.isinf(test[FEATURE_COLUMNS].to_numpy()).any()
        assert len(test) == cohort.count()
        # One prediction pass; county summaries reuse these same probabilities.
        probabilities = probability(final_pipeline, test[FEATURE_COLUMNS])
        predictions = test[['fips_code','timestamp','candidate_y']].copy()
        predictions['probability'] = probabilities
        predictions['prediction'] = (probabilities > .5).astype(int)
        predictions_path = artifact.with_name('final_predictions.parquet')
        predictions.to_parquet(predictions_path, index=False)
        sample = test[FEATURE_COLUMNS].iloc[np.linspace(0,len(test)-1,min(100,len(test)),dtype=int)].copy()
        sample['expected_probability'] = probability(final_pipeline, sample[FEATURE_COLUMNS])
        sample['expected_prediction'] = final_pipeline.predict(sample[FEATURE_COLUMNS])
        sample_path = artifact.with_name('reload_sample.parquet')
        sample.to_parquet(sample_path, index=False)
        result = {'status': 'VERIFIED_FINAL_EVALUATION', 'utc': datetime.now(timezone.utc).isoformat(),
                  'selection': selection, 'development_rows': len(frame), 'final_refit_seconds': seconds, 'warnings': messages,
                  'source_sha256': source_sha, 'extraction': extraction, 'cleaning': counts, 'coverage': coverage,
                  'label_exclusions': labels.count()-len(test),
                  'label_counts': [row.asDict() for row in labels.groupBy('split','future_slots','candidate_y').count().collect()],
                  'metrics': classification_metrics(test.candidate_y, probabilities),
                  'county_metrics': {county: classification_metrics(group.candidate_y, group.probability)
                                     for county,group in predictions.groupby('fips_code')},
                  'artifact': artifact.relative_to(root).as_posix(), 'artifact_sha256': digest(artifact),
                  'predictions': predictions_path.relative_to(root).as_posix(), 'predictions_sha256': digest(predictions_path),
                  'reload_sample': sample_path.relative_to(root).as_posix(), 'reload_sample_sha256': digest(sample_path),
                  'features': FEATURE_COLUMNS, 'final_evaluation_count': 1,
                  'limitations': development['limitations'][:3] + ['Historical reported escalation, not causal restoration or operational risk',
                    'Final features use only observed 2022 past/current history; no fitting or selection on 2022']}
        result_path = root/'reports/modeling/final_evaluation.json'
        write_json(result_path, result)
        write_json(journal_path, {'status':'COMPLETE','utc':datetime.now(timezone.utc).isoformat(),
                                 'selection':selection,'result_sha256':digest(result_path)})
        progress(root, 'final_evaluation_complete', result['metrics'])
        return result
    except Exception as error:
        write_json(journal_path, {'status':'FAILED','utc':datetime.now(timezone.utc).isoformat(),
                                 'selection':selection,'error':repr(error),'repeat_forbidden':True})
        raise
    finally:
        if spark is not None:
            spark.stop()


def verify_reload(root):
    """Fresh Python interpreter; no raw test data or refitting in reload check."""
    root = Path(root).resolve()
    subprocess.run([sys.executable, str(root/'scripts/reload_model.py')], cwd=root, check=True)
    return json.loads((root/'reports/modeling/reload_validation.json').read_text(encoding='utf-8'))

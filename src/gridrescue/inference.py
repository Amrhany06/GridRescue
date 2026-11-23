"""Freeze and score the GridRescue development pipeline outside notebook display code."""
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .experiment import digest, fit, probability, write_json
from .modeling import FEATURE_COLUMNS, make_model

METADATA = Path('reports/modeling/frozen_pipeline.json')
RELOAD_REPORT = Path('reports/modeling/development_reload.json')


def load_frozen_pipeline(root, metadata=None):
    """Load the project's fitted imputer, scaler and classifier after checking their hash."""
    if metadata is None:
        metadata = json.loads((root / METADATA).read_text(encoding='utf-8'))
    path = root / metadata['artifact']
    if metadata['features'] != FEATURE_COLUMNS or digest(path) != metadata['artifact_sha256']:
        raise ValueError('Frozen artifact schema or hash mismatch')
    return joblib.load(path)


def predict_escalation(pipeline, features):
    """Return binary labels and escalation scores from ordered Task 2 predictors."""
    if list(features.columns) != FEATURE_COLUMNS or features.empty:
        raise ValueError('Supply nonempty data in the exact 13-feature order')
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in features.dtypes):
        raise ValueError('Predictors must be numeric')
    if np.isinf(features.to_numpy(dtype=float, na_value=np.nan)).any():
        raise ValueError('Predictors must be finite or missing before imputation')
    # Serial prediction makes the forest add tree probabilities in a stable order.
    with joblib.parallel_config(backend='sequential', n_jobs=1):
        scores = probability(pipeline, features)
    return pd.DataFrame({'prediction': (scores > .5).astype(int), 'score': scores}, index=features.index)


def freeze_pipeline(root, frame, selection, approval):
    """Refit the frozen choice on allowed development rows and save its reload fixture."""
    if not selection.get('frozen') or selection.get('features') != FEATURE_COLUMNS:
        raise ValueError('A frozen selection with the approved feature order is required')
    if set(frame.split) != {'train', 'validation'}:
        raise ValueError('Freeze expects training and validation rows only')
    metadata_path = root / METADATA
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata['selection'] != selection:
            raise ValueError('Existing artifact belongs to a different frozen selection')
        load_frozen_pipeline(root, metadata)
        return metadata

    pipeline = make_model(selection['model'], selection['parameters'])
    seconds, warnings = fit(pipeline, frame[FEATURE_COLUMNS], frame.candidate_y)
    directory = root / 'artifacts/modeling'
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / 'frozen_development_pipeline.joblib'
    sample_path = directory / 'development_reload_sample.parquet'
    sample = frame.iloc[np.linspace(0, len(frame) - 1, min(100, len(frame)), dtype=int)][FEATURE_COLUMNS].copy()
    expected = predict_escalation(pipeline, sample)
    joblib.dump(pipeline, artifact, compress=3)
    sample.assign(expected_prediction=expected.prediction, expected_score=expected.score).to_parquet(sample_path, index=False)
    metadata = {
        'selection': selection, 'features': FEATURE_COLUMNS, 'development_rows': len(frame),
        'fit_seconds': seconds, 'warnings': warnings, 'decision_threshold': .5, 'ties_predict': 0,
        'classifier_parameters': pipeline.named_steps['classifier'].get_params(),
        'target': approval, 'artifact': artifact.relative_to(root).as_posix(), 'artifact_sha256': digest(artifact),
        'reload_sample': sample_path.relative_to(root).as_posix(), 'reload_sample_sha256': digest(sample_path),
        'versions': {name: importlib.metadata.version(name) for name in ('scikit-learn', 'joblib', 'pandas', 'numpy')},
    }
    write_json(metadata_path, metadata)
    return metadata


def verify_development_reload(root):
    """Invoke reload verification in a clean interpreter using only the frozen artifact and fixture."""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    subprocess.run([sys.executable, '-m', 'gridrescue.inference', str(root)], env=environment, check=True)
    return json.loads((root / RELOAD_REPORT).read_text(encoding='utf-8'))


def _verify_reload(root):
    """Compare saved fixture labels and scores bit-for-bit inside the new interpreter."""
    metadata = json.loads((root / METADATA).read_text(encoding='utf-8'))
    pipeline = load_frozen_pipeline(root, metadata)
    sample_path = root / metadata['reload_sample']
    if digest(sample_path) != metadata['reload_sample_sha256']:
        raise ValueError('Reload fixture hash mismatch')
    sample = pd.read_parquet(sample_path)
    actual = predict_escalation(pipeline, sample[FEATURE_COLUMNS])
    np.testing.assert_array_equal(actual.prediction, sample.expected_prediction)
    np.testing.assert_array_equal(actual.score, sample.expected_score)
    write_json(root / RELOAD_REPORT, {
        'status': 'VERIFIED', 'fresh_process': True, 'pid': os.getpid(), 'python': sys.executable,
        'rows': len(sample), 'features': FEATURE_COLUMNS, 'maximum_score_error': 0.,
        'artifact_sha256': metadata['artifact_sha256'], 'refit': False, 'holdout_accessed': False,
    })


if __name__ == '__main__':
    _verify_reload(Path(sys.argv[1]).resolve())

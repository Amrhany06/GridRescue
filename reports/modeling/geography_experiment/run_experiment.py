"""Compare three Random Forest feature sets on the approved development cohort."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from gridrescue.experiment import development_source, digest, fingerprint, fit, load_development, probability, write_json
from gridrescue.modeling import FEATURE_COLUMNS, chronological_folds, classification_metrics, make_model

PARAMETERS = {'n_estimators': 100, 'max_depth': 12, 'min_samples_leaf': 10}
VARIANTS = {'baseline': None, 'state': 'state', 'fips': 'fips_code'}
METRICS = ['average_precision', 'accuracy', 'precision', 'recall', 'f1', 'roc_auc']
REPRODUCTION_TOLERANCE = 1e-6


def add_state(frame, metadata):
    """Attach verified county-to-state metadata without changing eligible row order."""
    states = metadata[['fips_code', 'state']].drop_duplicates()
    codes = states.fips_code
    if not codes.map(lambda code: isinstance(code, str) and len(code) == 5 and code.isascii() and code.isdigit()).all():
        raise ValueError('Geography requires five-character string FIPS codes')
    if states.fips_code.duplicated().any() or not states.state.map(lambda state: isinstance(state, str) and bool(state)).all():
        raise ValueError('Each county must have one state in the source metadata')
    if set(states.fips_code) != set(frame.fips_code):
        raise ValueError('Geography metadata must match the approved county cohort')
    return frame.assign(state=frame.fips_code.map(states.set_index('fips_code').state))


def make_variant(category):
    """Extend the existing numeric pipeline with one optional fold-fitted encoder."""
    model = make_model('Random Forest', PARAMETERS)
    if category is not None:
        prepare = model.named_steps['prepare']
        encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
        prepare.set_params(transformers=[*prepare.transformers, ('geography', encoder, [category])])
    return model


def fit_variant(variant, train, evaluation):
    """Fit an independent pipeline, then measure it on the fixed evaluation rows."""
    category = VARIANTS[variant]
    inputs = FEATURE_COLUMNS if category is None else [*FEATURE_COLUMNS, category]
    model = make_variant(category)
    seconds, messages = fit(model, train[inputs], train.candidate_y)
    scores = probability(model, evaluation[inputs])
    learned = [] if category is None else model.named_steps['prepare'].named_transformers_['geography'].categories_[0].tolist()
    estimator = model.named_steps['classifier']
    details = {'train_rows': len(train), 'training_seconds': seconds, 'warnings': messages,
               'learned_categories': learned, 'feature_count': estimator.n_features_in_,
               'features_sampled_per_split': estimator.estimators_[0].max_features_,
               'unseen_evaluation_rows': 0 if category is None else int((~evaluation[category].isin(learned)).sum())}
    return scores, details


def score_period(name, variant, predictions, scores, details):
    """Calculate common metrics and fixed-order confusion matrices overall and by county."""
    scored = predictions.assign(score=scores)
    groups = [('all', scored), *scored.groupby('fips_code', sort=True)]
    return [{'period': name, 'variant': variant, 'county_fips': code,
             **classification_metrics(group.candidate_y, group.score),
             'training_seconds': details['training_seconds'] if code == 'all' else None}
            for code, group in groups]


def plot_results(results, output):
    """Plot paired AP differences on the folds and separate 2021 county outcomes."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    use = results[results.variant.ne('baseline')]
    folds = use[(use.period != '2021') & (use.county_fips == 'all')]
    counties = use[(use.period == '2021') & (use.county_fips != 'all')]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for data, key, axis, title in [(folds, 'period', axes[0], 'Chronological folds'),
                                   (counties, 'county_fips', axes[1], '2021 by county')]:
        paired = data.pivot(index=key, columns='variant', values='delta_average_precision')[['state', 'fips']]
        paired.plot.bar(ax=axis, color=['#237e89', '#ee9f3c'], rot=0)
        axis.axhline(0, color='#1c2838', linewidth=1)
        axis.set(title=title, xlabel='', ylabel='AP change from 13-feature baseline')
        axis.legend(handles=axis.containers, labels=['State', 'FIPS'])
    fig.savefig(output / 'paired_ap.png', dpi=160)
    plt.close(fig)


def run(output):
    """Reproduce the published 2021 result before any geography fitting."""
    model_reports = ROOT / 'reports/modeling'
    frozen_path = model_reports / 'frozen_selection.json'
    baseline_path = model_reports / 'random_forest_cv_selected.json'
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    development_hash, source_info = fingerprint(ROOT)
    if (frozen['model'] != 'Random Forest' or frozen['parameters'] != PARAMETERS
            or frozen['features'] != FEATURE_COLUMNS or frozen['fingerprint'] != development_hash
            or baseline['validation']['decision_threshold'] != 0.5
            or make_variant(None).named_steps['classifier'].get_params() != baseline['classifier_parameters']):
        raise ValueError('Saved feature, classifier, threshold or development contract differs')
    protected = {str(path.relative_to(ROOT)): digest(path) for path in (
        frozen_path, baseline_path, model_reports / 'frozen_pipeline.json',
        *sorted((ROOT / 'notebooks').glob('*.ipynb')),
        ROOT / 'artifacts/modeling/frozen_development_pipeline.joblib',
        ROOT / baseline['artifact'], ROOT / baseline['predictions'],
    )}
    if digest(ROOT / baseline['artifact']) != baseline['artifact_sha256'] or digest(ROOT / baseline['predictions']) != baseline['predictions_sha256']:
        raise ValueError('Saved baseline artifact or prediction digest differs')

    frame = load_development(ROOT)
    source, parts, _ = development_source(ROOT)
    metadata = pd.read_parquet([source['label_audit'] / name for name, _ in parts], columns=['fips_code', 'state'])
    frame = add_state(frame, metadata)
    mapping = frame[['fips_code', 'state']].drop_duplicates().sort_values('fips_code')
    if len(mapping) != 3 or mapping.state.nunique() != 3:
        raise ValueError('The experiment expects three counties each in a distinct state')

    folds = chronological_folds(frame)
    train = frame.loc[frame.split == 'train']
    validation = frame.loc[frame.split == 'validation']
    identity = ['fips_code', 'timestamp', 'candidate_y']
    prior_predictions = pd.read_parquet(ROOT / baseline['predictions'])
    if not validation[identity].reset_index(drop=True).equals(prior_predictions[identity]):
        raise ValueError('2021 row identity or labels differ from the recorded baseline')

    baseline_scores, baseline_details = fit_variant('baseline', train, validation)
    measured = classification_metrics(validation.candidate_y, baseline_scores)
    expected_ap = frozen['validation_average_precision']
    ap_delta = measured['average_precision'] - expected_ap
    reproduction = {'status': 'PASS' if abs(ap_delta) <= REPRODUCTION_TOLERANCE else 'FAIL',
                    'recorded_ap': expected_ap, 'reproduced_ap': measured['average_precision'], 'ap_delta': ap_delta,
                    'absolute_tolerance': REPRODUCTION_TOLERANCE, 'rows_and_labels_identical': True,
                    'max_absolute_score_change': float(np.max(np.abs(baseline_scores - prior_predictions.probability))),
                    'training_seconds': baseline_details['training_seconds']}
    write_json(output / 'baseline_reproduction.json', reproduction)
    print(json.dumps(reproduction), flush=True)
    if reproduction['status'] != 'PASS':
        raise RuntimeError('The 2021 baseline did not reproduce. Geography fits are gated.')

    periods = [('2021', train, validation), *[(fold['name'], frame.iloc[fold['train']], frame.iloc[fold['validation']]) for fold in folds]]
    records, fits, partition_info = [], [], []
    for name, train_rows, evaluation in periods:
        predictions = evaluation[[*identity, 'state']].copy()
        partition_info.append({'period': name, 'train_rows': len(train_rows), 'evaluation_rows': len(evaluation),
                               'last_train_utc': train_rows.timestamp.max().isoformat(),
                               'first_evaluation_utc': evaluation.timestamp.min().isoformat(),
                               'last_evaluation_utc': evaluation.timestamp.max().isoformat()})
        for variant in VARIANTS:
            if name == '2021' and variant == 'baseline':
                scores, details = baseline_scores, baseline_details
            else:
                print(f'Fitting {variant} in {name} on {len(train_rows):,} rows', flush=True)
                scores, details = fit_variant(variant, train_rows, evaluation)
            fits.append({'period': name, 'variant': variant, **details})
            records.extend(score_period(name, variant, predictions, scores, details))
            predictions[f'{variant}_score'] = scores
        predictions.to_parquet(output / f'predictions_{name}.parquet', index=False)

    results = pd.DataFrame(records)
    baseline_metrics = results[results.variant == 'baseline'].set_index(['period', 'county_fips'])
    paired_keys = pd.MultiIndex.from_frame(results[['period', 'county_fips']])
    for metric in METRICS:
        results[f'delta_{metric}'] = results[metric] - baseline_metrics.loc[paired_keys, metric].to_numpy()
    results.to_csv(output / 'metrics.csv', index=False)
    cv = results[results.period.ne('2021')]
    summary = cv.groupby(['variant', 'county_fips'])[[*METRICS, *[f'delta_{m}' for m in METRICS]]].agg(['mean', 'std'])
    summary.to_csv(output / 'cv_summary.csv')
    plot_results(results, output)

    if any(digest(ROOT / name) != sha for name, sha in protected.items()):
        raise RuntimeError('A protected baseline file changed during the run')
    write_json(output / 'execution.json', {'status': 'VERIFIED', 'data_and_versions': source_info,
               'frozen_classifier': baseline['classifier_parameters'], 'features': FEATURE_COLUMNS,
               'county_to_state': mapping.to_dict('records'), 'partitions': partition_info, 'fits': fits,
               'encoder': 'Dense one-hot, training partition only, unknown category encoded as all zeros',
               'threshold': 0.5, 'threshold_tie_predicts': 0, 'protected_hashes': protected,
               'holdout_accessed': False})


if __name__ == '__main__':
    directory = HERE / datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S%fZ')
    directory.mkdir()
    print(f'Results: {directory}', flush=True)
    run(directory)

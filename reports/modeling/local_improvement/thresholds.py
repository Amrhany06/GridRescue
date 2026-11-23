"""Select strict score cutoffs using chronological out-of-fold predictions."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = HERE.parent / 'county_expansion'
RUN = 'pilot_20_20261121'
BASE_REPORT = PRIOR / RUN
BASE_DATA = ROOT / 'artifacts/modeling/county_expansion' / RUN
ARTIFACTS = ROOT / 'artifacts/modeling/local_improvement'
FOLDS = ('2018_H2', '2019', '2020')
KEY = ['fips_code', 'timestamp', 'candidate_y']


def ratio(a, b):
    """Divide counts, returning zero for an empty denominator."""
    return np.divide(a, np.where(b == 0, 1, b))


def operating_metrics(tp, fp, tn, fn):
    """Compute decision metrics from the four confusion-matrix counts."""
    rows = tp + fp + tn + fn
    recall = ratio(tp, tp + fn)
    return dict(accuracy=ratio(tp + tn, rows), recall=recall, precision=ratio(tp, tp + fp),
                f1=ratio(2 * tp, 2 * tp + fp + fn), f2=ratio(5 * tp, 5 * tp + fp + 4 * fn),
                balanced_accuracy=(recall + ratio(tn, tn + fp)) / 2,
                false_alarms_per_1000=1000 * ratio(fp, rows), tp=tp, fp=fp, tn=tn, fn=fn,
                predicted=tp + fp)


def checked_arrays(y, score):
    """Accept matching non-empty label and probability vectors with valid values."""
    y, score = np.asarray(y), np.asarray(score, dtype=float)
    if (y.ndim != 1 or score.shape != y.shape or not len(y) or not np.isin(y, [0, 1]).all()
            or not np.isfinite(score).all() or ((score < 0) | (score > 1)).any()):
        raise ValueError('Invalid binary labels or model probabilities')
    return y.astype(np.int64, copy=False), score


def threshold_curve(y, score):
    """Sort once and evaluate every distinct decision including tied scores together."""
    y, score = checked_arrays(y, score)
    if y.min() == y.max():
        raise ValueError('Selecting thresholds requires both classes')
    order = np.argsort(-score, kind='stable')
    sorted_score = score[order]
    # Each endpoint includes every row with the same score before it.
    ends = np.flatnonzero(np.r_[sorted_score[:-1] != sorted_score[1:], True])
    tp = np.r_[0, y[order].cumsum()[ends]]
    fp = np.r_[0, ends + 1] - tp
    # Move one float below each score to honor the original strict > decision.
    cutoff = np.r_[1., np.nextafter(sorted_score[ends], -np.inf)]
    return pd.DataFrame({'threshold': cutoff, **operating_metrics(tp, fp, len(y) - y.sum() - fp, y.sum() - tp)})


def select_thresholds(curve):
    """Select objectives from OOF only. Score ties prefer the stricter cutoff."""
    selections = {'fixed_050': 0.5}
    for objective in ('f2', 'balanced_accuracy'):
        selections[objective] = float(curve.loc[curve[objective].idxmax(), 'threshold'])
    for target in (50, 60, 70):
        eligible = curve[curve.recall >= target / 100]
        selections[f'accuracy_recall_{target}'] = float(curve.loc[eligible.accuracy.idxmax(), 'threshold'])
    return selections


def pareto(curve):
    """Keep the highest-recall point per accuracy and every non-dominated point."""
    reversed_curve = curve.iloc[::-1]
    best_at_recall = reversed_curve.groupby('recall', sort=False).accuracy.transform('max')
    unique = reversed_curve[reversed_curve.accuracy.eq(best_at_recall)].drop_duplicates('recall', keep='last')
    return unique[unique.accuracy.gt(unique.accuracy.cummax().shift(fill_value=-1))].iloc[::-1]


def ranking(y, score):
    """Return threshold-independent metrics, with undefined values for single-class groups."""
    both = y.min() != y.max()
    return {'average_precision': float(average_precision_score(y, score)) if both else None,
            'roc_auc': float(roc_auc_score(y, score)) if both else None}


def metrics(y, score, threshold, rank=None):
    """Measure a fixed operating point and optionally reuse matching ranking metrics."""
    y, score = checked_arrays(y, score)
    chosen = score > threshold
    tp = int(y[chosen].sum())
    fp = int(chosen.sum()) - tp
    fn = int(y.sum()) - tp
    tn = len(y) - tp - fp - fn
    result = operating_metrics(tp, fp, tn, fn)
    if y.min() == y.max():
        result['balanced_accuracy'] = None
    return {'threshold': threshold, 'rows': len(y), 'positive': int(y.sum()),
            'prevalence': float(y.mean()), **result, **(ranking(y, score) if rank is None else rank)}


def score_groups(frame, variant, rules, groups, period):
    """Score every rule on identical row masks and rank probabilities once per group."""
    records = []
    for group, mask in groups.items():
        y = frame.candidate_y.to_numpy()[mask]
        score = frame[variant].to_numpy()[mask]
        rank = ranking(y, score)
        records.extend(dict(period=period, variant=variant, group=group, rule=rule,
                            **metrics(y, score, cutoff, rank)) for rule, cutoff in rules.items())
    return records


def write_json(path, content):
    """Create new evidence without replacing a previous run."""
    with path.open('x', encoding='utf-8') as out:
        json.dump(content, out, indent=2, allow_nan=False)


def prior_scores(period):
    """Read archive scores, restricting input to the three OOF folds or 2021."""
    if period not in (*FOLDS, '2021'):
        raise ValueError('Unknown development prediction period')
    frame = pd.read_parquet(BASE_REPORT / 'model_results' / f'predictions_{period}.parquet')
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    return frame


def metadata():
    """Read the original five-state roles and identifiers without reading outcomes."""
    return pd.DataFrame(json.loads((BASE_REPORT / 'cohort.json').read_text(encoding='utf-8'))['county_selection'])


def run(output):
    """Freeze four RF operating rules before opening archived 2021 scores."""
    sys.path.insert(0, str(PRIOR))
    from train_cohort import VARIANTS, masks

    output.mkdir()
    cohort = metadata()
    archived = {period: prior_scores(period) for period in FOLDS}
    for period, frame in archived.items():
        start = '2018-07-01' if period == '2018_H2' else f'{period}-01-01'
        bound = f'{int(period[:4]) + 1}-01-01'
        if (not frame.timestamp.ge(pd.Timestamp(start, tz='UTC')).all()
                or not (frame.timestamp + pd.Timedelta(hours=3)).lt(pd.Timestamp(bound, tz='UTC')).all()):
            raise ValueError(f'OOF timestamps outside purged fold {period}')
    combined = pd.concat(archived.values(), ignore_index=True)
    valid_codes = set(cohort.loc[cohort.role.eq('seen'), 'fips_code'])
    if combined.duplicated(KEY[:2]).any() or set(combined.fips_code) != valid_codes:
        raise ValueError('OOF archive has overlapping rows or incorrect geographic roles')
    y = combined.candidate_y.to_numpy()
    caps = {}
    quantiles = {}
    for variant in VARIANTS:
        score = combined[variant].to_numpy()
        curve = threshold_curve(y, score)
        caps[variant] = select_thresholds(curve)
        pareto(curve).to_csv(output / f'pareto_{variant}.csv', index=False, mode='x')
        quantiles[variant] = np.quantile(score[y == 1], [.1, .25, .5, .75, .9]).tolist()
    write_json(output / 'frozen_thresholds.json', caps)
    write_json(output / 'oof_positive_quantiles.json', quantiles)

    records = []
    archived['pooled_oof'] = combined
    archived['2021'] = prior_scores('2021')
    for period, frame in archived.items():
        groups = masks(frame, cohort) if period == '2021' else {'all': np.ones(len(frame), dtype=bool)}
        for variant, rules in caps.items():
            records.extend(score_groups(frame, variant, rules, groups, period))
    pd.DataFrame(records).to_csv(output / 'metrics.csv', index=False, mode='x')
    print(f'Thresholds fixed on {len(combined):,} OOF rows, applied to {len(archived["2021"]):,} development rows.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=HERE / 'threshold_results', type=Path)
    run(parser.parse_args().output)

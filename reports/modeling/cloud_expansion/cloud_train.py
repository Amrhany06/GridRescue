"""Sequential, fixed-configuration CPU fits and matched development evaluation."""
import gc
from datetime import timedelta
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve

from cloud_core import GIB, load, require_resources, save, validate_training_counties
from cloud_data import COLUMNS, HERE, KEY, NUMERIC, exact_period, fingerprint, read_rows
from train_local import XGB_SETTINGS, fit, masks, memory_measurement, metrics, model_for, probability
from thresholds import ranking
from gridrescue.modeling import FEATURE_COLUMNS

MODEL = 'xgb_history_state'
FEATURE_INPUTS = [*NUMERIC, 'state']


def training_budget(rows, width):
    """Plan space for Arrow, sklearn arrays and histogram training headroom."""
    return round(2.5 + rows * (4 * 8 * width + 400) / GIB, 2)


def fold_bounds(folds, fold):
    name, lo, end = next(item for item in folds if item[0] == fold)
    embargo = pd.DateOffset(hours=3)
    start, stop = pd.Timestamp(lo, tz='UTC'), pd.Timestamp(end, tz='UTC')
    return name, start, stop, start - embargo, stop - embargo


def recall_cutoffs(labels, scores, targets):
    """The kth-highest positive score gives the first crossing of each recall target."""
    y, p = np.asarray(labels), np.asarray(scores, dtype='float64')
    if y.ndim != 1 or y.shape != p.shape or set(np.unique(y)) != {0, 1} or not np.isfinite(p).all() or not ((0 <= p) & (p <= 1)).all():
        raise ValueError('Threshold selection needs aligned binary labels and finite scores')
    positive = np.sort(p[y == 1])
    return {f'target_{goal}': float(np.nextafter(positive[-((goal * len(positive) + 99) // 100)], -np.inf))
            for goal in targets}


def checked_training(frame, counties, withheld, lo, end):
    exact_period(frame, lo, end)
    codes = sorted(frame.fips_code.unique())
    validate_training_counties(codes, withheld)
    if not set(codes) <= set(counties) or not frame.future_slots.eq(12).all() or not frame.customers_out_t.gt(0).all():
        raise ValueError('Training rows do not satisfy the geography or label eligibility contract')
    return fingerprint(frame)


def training_frame(paths, counties, start, end):
    frame = read_rows(paths, counties, COLUMNS, start, end)
    for col in FEATURE_COLUMNS:
        frame[col] = frame[col].astype(float)
    return frame


def fitted(train, depth, output):
    model = model_for(MODEL, depth)
    t = time.perf_counter()
    with memory_measurement() as memory:
        _, warnings = fit(model, train, train.candidate_y)
    joblib.dump(model, output / 'pipeline.joblib', compress=3)
    model.named_steps['classifier'].save_model(output / 'booster.ubj')
    return model, {'fit_seconds': time.perf_counter() - t, 'warnings': warnings, **memory}


def flag_workload(frame, predictions):
    """Count runs of consecutive flags on the same county, as a workload proxy."""
    chosen = frame.loc[predictions, KEY].sort_values(['fips_code', 'timestamp']).reset_index(drop=True)
    if chosen.empty:
        return {'flagged_rows': 0, 'flag_runs': 0, 'runs_all_rows_negative': 0}
    adjacent = (chosen.fips_code.eq(chosen.fips_code.shift()) &
                chosen.timestamp.diff().eq(timedelta(minutes=15)))
    positives_by_run = chosen.candidate_y.groupby((~adjacent).cumsum()).sum()
    return {'flagged_rows': len(chosen), 'flag_runs': len(positives_by_run),
            'runs_all_rows_negative': int(positives_by_run.eq(0).sum())}


def record(y, score, cutoff, rank=None):
    measured = metrics(y, score, cutoff, rank)
    denominator = measured['tn'] + measured['fp']
    return {**measured, 'false_positive_rate': measured['fp'] / denominator if denominator else None}


def preprocessing_snapshot(model, sample):
    prepare = model.named_steps['prepare']
    geography = prepare.named_transformers_['geography']
    return {'columns': prepare.get_feature_names_out().tolist(),
            'states': geography.categories_[0].tolist(),
            'transformed': prepare.transform(sample[FEATURE_INPUTS]).tolist()}


def verify_preprocessing(model, sample, expected):
    actual = preprocessing_snapshot(model, sample)
    if any(actual[key] != expected[key] for key in ('columns', 'states')):
        raise AssertionError('Tier A encoding or feature order differs')
    np.testing.assert_allclose(actual['transformed'], expected['transformed'], rtol=1e-8, atol=1e-8)


class Training:
    def __init__(self, datasets, spec):
        self.data, self.spec = datasets, spec
        if spec['features'] != NUMERIC or spec['xgboost'] != dict(XGB_SETTINGS, max_depth=6):
            raise ValueError('Cloud feature contract or fixed XGBoost settings differ from Windows')
        if spec['recall_targets'] != [40, 50, 60]:
            raise ValueError('Unexpected OOF recall constraints')
        self.depth = spec['xgboost']['max_depth']

    def inputs(self, tier):
        pilot = load(self.data.stage('pilot-verified') / 'dataset.json')
        if tier == 'A':
            count = self.data.reference['train']['overall']['rows']
            states = sorted({r['state'] for r in self.data.reference['counties'] if r['role'] == 'seen'})
            return pilot['pilot'], {'rows': count, 'counties': self.data.seen, 'states': states}, pilot
        expanded = load(self.data.stage('expansion-verified') / 'dataset.json')
        evidence = expanded['tiers'][tier]
        b = expanded['tiers']['B']
        if abs(b['rows'] - 3_000_000) > self.spec['expansion']['tier_b_tolerance_rows']:
            raise ValueError(f'Tier B has {b["rows"]:,} eligible rows, outside 2.8–3.2M. Review the frozen dataset manifest.')
        if tier == 'C' and (evidence['rows'] <= b['rows'] or evidence['rows'] > 8_000_000):
            raise ValueError(f'Tier C must add eligible rows beyond Tier B and stay at or below 8M: {evidence["rows"]:,}')
        validate_training_counties(evidence['counties'], self.data.withheld)
        self.data.stage('tier-A-parity')
        chosen = {expanded['feature_stage_by_county'][code] for code in evidence['counties'] if code not in self.data.seen}
        return [*pilot['pilot'], *sorted(chosen)], evidence, pilot

    def train(self, tier):
        stages, plan, _ = self.inputs(tier)
        counties = plan['counties']
        paths = self.data.paths(stages, 'train')
        width = len(NUMERIC) + len(plan['states'])
        ram = training_budget(plan['rows'], width)
        print(f'Tier {tier}: {plan["rows"]:,} eligible rows, {len(counties)} counties, {width} encoded inputs.')
        results = []
        for fold, _, _ in self.spec['folds']:
            name, start, end, fit_end, valid_end = fold_bounds(self.spec['folds'], fold)

            def fold_fit(out, name=name, start=start, end=end, fit_end=fit_end, valid_end=valid_end):
                require_resources(self.data.vm, ram, 7, f'Tier {tier} {name} fit')
                train = training_frame(paths, counties, None, fit_end)
                train_fp = checked_training(train, counties, self.data.withheld, '2018-01-01', start.date().isoformat())
                if tier == 'A' and train_fp != self.data.reference['folds'][name]['train']:
                    raise ValueError(f'Tier A fit rows differ in {name}')
                model, timing = fitted(train, self.depth, out)
                del train
                gc.collect()
                valid = training_frame(paths, counties, start, valid_end)
                valid_fp = checked_training(valid, counties, self.data.withheld, start.date().isoformat(), end.date().isoformat())
                if tier == 'A' and valid_fp != self.data.reference['folds'][name]['validation']:
                    raise ValueError(f'Tier A fold validation rows differ in {name}')
                predictions = probability(model, valid)
                restored = joblib.load(out / 'pipeline.joblib')
                np.testing.assert_array_equal(probability(restored, valid[FEATURE_INPUTS].iloc[::997]), predictions[::997])
                valid[KEY].assign(score=predictions).to_parquet(out / 'scores.parquet', index=False)
                save(out / 'fit.json', dict(**timing, train=train_fp, oof=valid_fp,
                                            ap=float(average_precision_score(valid.candidate_y, predictions))))

            results.append(self.data.stage(f'tier-{tier}-{name}', fold_fit))

        def choose(out):
            predictions = pd.concat([pd.read_parquet(p / 'scores.parquet') for p in results], ignore_index=True)
            fp = fingerprint(predictions)
            labels, scores = predictions.candidate_y.to_numpy(), predictions.score.to_numpy(dtype='float64')
            thresholds = recall_cutoffs(labels, scores, self.spec['recall_targets'])
            rank = ranking(labels, scores)
            selected = {rule: record(labels, scores, cutoff, rank) for rule, cutoff in thresholds.items()}
            save(out / 'thresholds.json', dict(tier=tier, scope='training-period chronological OOF only', oof=fp,
                  cutoffs=thresholds, measured_oof=selected,
                  fold_ap={entry.name.removeprefix(f'tier-{tier}-'): load(entry/'fit.json')['ap'] for entry in results}))
        self.data.stage(f'tier-{tier}-thresholds', choose)

        def final_fit(out):
            require_resources(self.data.vm, ram, 7, f'Tier {tier} final fit')
            train = training_frame(paths, counties, None, None)
            observed = checked_training(train, counties, self.data.withheld, '2018-01-01', '2021-01-01')
            if set(train.fips_code) != set(counties) or observed['rows'] != plan['rows']:
                raise ValueError('Final fit data do not match the frozen tier manifest')
            if tier == 'A' and observed != self.data.reference['train']['overall']:
                raise ValueError('Cloud benchmark training anchors differ from the local experiment')
            model, timing = fitted(train, self.depth, out)
            check_rows = train.iloc[::997][FEATURE_INPUTS]
            restored = joblib.load(out / 'pipeline.joblib')
            np.testing.assert_array_equal(probability(model, check_rows), probability(restored, check_rows))
            save(out / 'fit.json', dict(**timing, tier=tier, plan=plan, training=observed,
                                        pipeline_reload_rows=len(check_rows)))
        return self.data.stage(f'tier-{tier}-final', final_fit)

    def evaluate(self, tier):
        _, plan, pilot = self.inputs(tier)
        selected = load(self.data.stage(f'tier-{tier}-thresholds') / 'thresholds.json')
        final = self.data.stage(f'tier-{tier}-final')

        def run(out):
            require_resources(self.data.vm, 3, 3, f'Tier {tier} development evaluation')
            paths = self.data.paths(pilot['pilot'], 'validation')
            rows = training_frame(paths, sorted(self.data.roles), None, None)
            exact_period(rows, '2021-01-01', '2022-01-01')
            observed = fingerprint(rows)
            if observed != self.data.reference['validation']['overall']:
                raise ValueError('The 2021 evaluation rows or labels differ from the trusted population. Stop.')
            model = joblib.load(final / 'pipeline.joblib')
            parity = load(HERE / 'tier_a_parity_reference.json') if tier == 'A' else None
            if parity is not None:
                panel = pd.DataFrame(parity['features']['validation'])
                verify_preprocessing(model, panel, parity['preprocessing'])
                error = np.abs(probability(model, panel[FEATURE_INPUTS]).astype(float) - parity['scores'])
                save(out / 'prediction_panel.json', {'rows': len(panel), 'mean_abs_difference': float(error.mean()),
                                                     'max_abs_difference': float(error.max())})
            scores = probability(model, rows).astype('float64')
            scores_path = out / 'predictions.parquet'
            rows[KEY].assign(score=scores).to_parquet(scores_path, index=False)
            reloaded = pd.read_parquet(scores_path)
            if fingerprint(reloaded) != observed:
                raise ValueError('Persisted development rows or labels changed')
            np.testing.assert_array_equal(scores, reloaded.score.to_numpy())
            cohort = pd.DataFrame(self.data.reference['counties'])
            decisions, matched, workloads = [], [], []
            cutoffs = dict(selected['cutoffs'])
            if tier == 'A':
                cutoffs['local_incumbent_cutoff'] = self.spec['benchmark']['threshold']
            groups = masks(rows, cohort)
            groups.update({f'state_{state}': rows.state.eq(state).to_numpy() for state in sorted(rows.state.unique())})
            for group, group_mask in groups.items():
                sample = rows.loc[group_mask]
                y, p = sample.candidate_y.to_numpy(), scores[group_mask]
                ranked = ranking(y, p)
                for rule, cutoff in cutoffs.items():
                    decisions.append(dict(tier=tier, group=group, rule=rule, **record(y, p, cutoff, ranked)))
                    if group in ('all', 'seen', 'unseen_county', 'unseen_state'):
                        workloads.append(dict(tier=tier, group=group, rule=rule, **flag_workload(sample, p > cutoff)))
                for rule, coordinate in recall_cutoffs(y, p, self.spec['recall_targets']).items():
                    positive = (p > coordinate) & (y == 1)
                    matched.append(dict(tier=tier, group=group, recall_coordinate=int(rule[-2:]) / 100,
                                        achieved_recall=float(positive.sum()/y.sum()),
                                        precision=float(positive.sum()/(p > coordinate).sum())))
            pd.DataFrame(decisions).to_csv(out / 'metrics.csv', index=False)
            pd.DataFrame(matched).to_csv(out / 'matched_recall_descriptive.csv', index=False)
            pd.DataFrame(workloads).to_csv(out / 'flag_run_workload.csv', index=False)
            precision, recall, _ = precision_recall_curve(rows.candidate_y, scores, drop_intermediate=True)
            pd.DataFrame(dict(precision=precision, recall=recall)).to_parquet(out / 'precision_recall.parquet', index=False)
            save(out / 'evaluation.json', dict(tier=tier, training_plan=plan, development=observed,
                 thresholds_from=selected['scope'], post_fit=True, cutoffs=cutoffs,
                 flag_run_definition='Consecutive flagged 15-minute rows in one county, split by gaps. Runs are a proxy, with no incident labels.'))
        evaluation = self.data.stage(f'tier-{tier}-evaluation', run)
        if tier == 'A':
            def parity(out):
                table = pd.read_csv(evaluation / 'metrics.csv')
                measured = table.query('group == "all" and rule == "local_incumbent_cutoff"').iloc[0]
                reference = self.spec['benchmark']
                comparisons = {name: (float(measured[name]), reference[name], tol) for name, tol in
                               [('average_precision', .002), ('recall', .01), ('precision', .01), ('accuracy', .01)]}
                comparisons['false_positive_rows_per_1000'] = (float(measured.false_alarms_per_1000),
                                                                reference['false_positive_rows_per_1000'], 10.)
                deviations = {name: dict(cloud=cloud, windows=local, delta=cloud-local, max_abs_difference=tol)
                              for name, (cloud, local, tol) in comparisons.items()}
                if any(not np.isfinite(row['delta']) or abs(row['delta']) > row['max_abs_difference']
                       for row in deviations.values()):
                    raise ValueError(f'Tier A metric parity failed. Review platform reproducibility before expansion: {deviations}')
                states = table.loc[table.group.str.startswith('state_') & table.rule.eq('local_incumbent_cutoff')]
                local = load(HERE / 'tier_a_parity_reference.json')['state_metrics']
                state_deltas = {row.group: {key: float(getattr(row, key)) - local[row.group][key]
                                            for key in local[row.group]} for row in states.itertuples()}
                if set(state_deltas) != set(local):
                    raise ValueError('Tier A state parity results are incomplete')
                save(out / 'parity.json', {'overall_gates': deviations, 'state_deltas_descriptive': state_deltas,
                                           'prediction_panel_descriptive': load(evaluation / 'prediction_panel.json')})
            self.data.stage('tier-A-parity', parity)
        return evaluation

    def export(self, tiers, output):
        """Publish a small comparison folder; full checkpoint archives stay on Drive."""
        from matplotlib import pyplot as plt
        output.mkdir(parents=True, exist_ok=True)
        records = []
        fig, ax = plt.subplots(figsize=(8, 5), layout='constrained')
        reference = self.spec['benchmark']
        save(output / 'windows_benchmark.json', reference)
        ax.scatter(reference['recall'], reference['precision'], s=75, marker='x', label='Windows reference')
        for tier in tiers:
            path = self.data.stage(f'tier-{tier}-evaluation')
            evaluation = load(path / 'evaluation.json')
            if evaluation['development'] != self.data.reference['validation']['overall']:
                raise ValueError('Evaluation population changed across tiers')
            curve = pd.read_parquet(path / 'precision_recall.parquet')
            table = pd.read_csv(path / 'metrics.csv')
            records.append(table)
            ax.plot(curve.recall, curve.precision, label=f'Tier {tier}')
            selected = table.query('group == "all" and rule in ["target_40", "target_50", "target_60"]')
            ax.scatter(selected.recall, selected.precision)
            for filename in ('metrics.csv', 'matched_recall_descriptive.csv', 'flag_run_workload.csv', 'evaluation.json'):
                (output / f'{tier}_{filename}').write_bytes((path / filename).read_bytes())
        pd.concat(records, ignore_index=True).to_csv(output / 'comparison.csv', index=False)
        ax.set(xlabel='Actual recall', ylabel='Precision', title='Matched 2021 development precision–recall')
        ax.legend()
        fig.savefig(output / 'precision_recall.png', dpi=140)
        plt.close(fig)

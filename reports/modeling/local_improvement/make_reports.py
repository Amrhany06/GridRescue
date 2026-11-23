"""Render Markdown and static figures from the measured machine-readable results."""
import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from thresholds import ARTIFACTS, HERE

NAMES = {'numeric': 'Numerical', 'state': 'State', 'fips': 'FIPS', 'both': 'State + FIPS',
         'rf_original_state': 'RF original, State', 'rf_history_state': 'RF history, State',
         'rf_original_both': 'RF original, State + FIPS', 'rf_history_both': 'RF history, State + FIPS',
         'xgb_original_state': 'XGBoost original, State', 'xgb_history_state': 'XGBoost history, State'}
GROUPS = {'all': 'All 20', 'original': 'Original three', 'seen': 'Seen (12)',
          'other_seen': 'Other seen (9)', 'unseen_county': 'Unseen counties (4)', 'unseen_state': 'Unseen state, NY (4)'}
RULES = {'fixed_050': 'Fixed 0.50', 'f2': 'Best OOF F2', 'balanced_accuracy': 'Best OOF balanced accuracy',
         'accuracy_recall_50': 'Accuracy at OOF recall ≥50%', 'accuracy_recall_60': 'Accuracy at OOF recall ≥60%',
         'accuracy_recall_70': 'Accuracy at OOF recall ≥70%'}
PRACTICAL = 'accuracy_recall_60'


def read(path):
    """Read a completed evidence file."""
    return json.loads(path.read_text(encoding='utf-8'))


def save(name, body):
    """Write each report once so previous experiment evidence is preserved."""
    with (HERE / name).open('x', encoding='utf-8') as stream:
        stream.write(body.rstrip() + '\n')


def table(headers, rows):
    """Render a compact Markdown table from already formatted fields."""
    return ('| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join(['---'] * len(headers)) + ' |\n' +
            '\n'.join('| ' + ' | '.join(map(str, row)) + ' |' for row in rows))


def pct(value):
    return f'{100 * value:.2f}%'


def score_row(row):
    return [f'{row.threshold:.6f}', f'{row.average_precision:.6f}', pct(row.accuracy), pct(row.recall),
            pct(row.precision), pct(row.f1), pct(row.f2), pct(row.balanced_accuracy), f'{row.roc_auc:.6f}',
            f'{row.false_alarms_per_1000:.1f}', f'{int(row.tn):,}/{int(row.fp):,}/{int(row.fn):,}/{int(row.tp):,}']


SCORE_FIELDS = ['Cutoff', 'AP', 'Accuracy', 'Recall', 'Precision', 'F1', 'F2', 'Balanced acc.', 'ROC-AUC',
                'False alarms / 1,000', 'TN / FP / FN / TP']


def figure(fig, filename):
    """Save a new PNG without overwriting plotting evidence."""
    with (HERE / filename).open('xb') as stream:
        fig.savefig(stream, format='png', dpi=170, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def threshold_report():
    """Describe four existing forests and their unchanged out-of-time cutoff transfers."""
    output = HERE / 'threshold_results'
    numeric = pd.read_csv(output / 'metrics.csv')
    pooled = numeric[(numeric.period == 'pooled_oof') & (numeric.group == 'all')]
    new = numeric[(numeric.period == '2021') & (numeric.group == 'all')]
    quantiles = read(output / 'oof_positive_quantiles.json')
    reason = [[NAMES[variant], *(f'{x:.3f}' for x in numbers)] for variant, numbers in quantiles.items()]
    operating = []
    for row in pooled.itertuples():
        other = new[(new.variant == row.variant) & (new.rule == row.rule)].iloc[0]
        operating.append([NAMES[row.variant], RULES[row.rule], f'{row.threshold:.6f}', pct(row.accuracy), pct(row.recall),
                          pct(other.accuracy), pct(other.recall), pct(other.precision), f'{other.false_alarms_per_1000:.1f}'])
    main = new[(new.variant == 'both') & (new.rule == 'fixed_050')].iloc[0]
    practical = new[(new.variant == 'both') & (new.rule == PRACTICAL)].iloc[0]
    f2 = new[(new.variant == 'both') & (new.rule == 'f2')].iloc[0]
    save('THRESHOLD_DIAGNOSIS.md', f"""# Threshold diagnosis

The four existing 100-tree Random Forests scored 890,035 genuine out-of-fold observations in purged chronological folds (181,267 in 2018 H2, 358,402 in 2019, and 350,366 in 2020). Every rule below was selected on those scores and saved before the 582,532 archived 2021 scores were opened. There was no geographical holdout fitting. The 2021 positive prevalence was {pct(main.prevalence)}, giving an always-negative accuracy of {pct(1-main.prevalence)} with zero recall.

A positive prediction requires a probability score strictly greater than the cutoff. Forest probabilities average positive-class proportions across trees. The observed positive-score distribution, including the median {quantiles['both'][2]:.3f} for State + FIPS, clusters below 0.50. That rule called only {int(main.predicted):,} of {int(main.rows):,} rows positive and missed {int(main.fn):,} of the {int(main.positive):,} escalations. Score distributions can also shift across time or locations. A score is not a calibrated estimate of operational risk on the evidence available here.

{table(['Positive OOF scores', '10th pct.', '25th pct.', 'Median', '75th pct.', '90th pct.'], reason)}

## Transfer to 2021

{table(['Forest', 'OOF objective', 'Cutoff', 'OOF acc.', 'OOF recall', '2021 acc.', '2021 recall', '2021 precision', '2021 FP / 1,000'], operating)}

For State + FIPS, the 60% OOF recall rule moved 2021 recall by {(practical.recall-main.recall)*100:+.2f} percentage points and accuracy by {(practical.accuracy-main.accuracy)*100:+.2f} points. It caught {int(practical.tp-main.tp):,} additional escalations and produced {int(practical.fp-main.fp):,} additional false alarms. The F2 cutoff reached {pct(f2.recall)} recall with {f2.false_alarms_per_1000:.1f} false alarms per 1,000 observations. The 60% OOF target is a selection constraint on historical folds and does not guarantee 60% recall on future data.

F2 weights recall more than precision. Balanced accuracy averages recall for escalation and non-escalation. For the constrained cutoffs, the script evaluates every attainable grouping of equal scores and finds the highest-accuracy point satisfying the recall goal. Metric ties favor a higher cutoff. The Pareto frontier contains only points for which increasing recall requires giving up accuracy. False alarms are false positives divided by all observations, multiplied by 1,000. Changing a cutoff preserves the scores and ranking metrics.

![Out-of-fold recall and accuracy Pareto frontier](threshold_pareto.png)

[Per-fold, pooled and 2021 metrics including all county groups](threshold_results/metrics.csv) · [Frozen cutoffs](threshold_results/frozen_thresholds.json)
""")
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for name in ('numeric', 'state', 'fips', 'both'):
        data = pd.read_csv(output / f'pareto_{name}.csv')
        ax.plot(data.recall, data.accuracy, label=NAMES[name], linewidth=1.8)
    ax.set(xlabel='Recall on chronological OOF predictions', ylabel='Accuracy on the same predictions',
           title='Random Forest cutoff tradeoffs')
    ax.legend(frameon=False)
    ax.grid(alpha=.25)
    figure(fig, 'threshold_pareto.png')


def model_reports():
    """Report controlled feature and algorithm comparisons after the experiment finishes."""
    path = HERE / 'model_results'
    selected = read(path / 'selection.json')
    fits = read(path / 'full_fits.json')
    permuted = read(path / 'permutation_ap.json')
    history = read(ARTIFACTS / 'history/audit.json')
    results = pd.read_csv(path / 'metrics_2021.csv')
    overall = results.query("group == 'all'")
    base = overall.query("variant == 'rf_original_state' and rule == 'fixed_050'").iloc[0]
    chosen = selected['champion']
    picks = selected['selection']
    chosen_rule = overall[(overall.variant == chosen) & (overall.rule == PRACTICAL)].iloc[0]
    fixed = overall[(overall.variant == chosen) & (overall.rule == 'fixed_050')].iloc[0]
    training_rows = []
    verification = read(path / 'verification.json')
    for name, fit in fits.items():
        if fit.get('source') == 'archived':
            previous = fit['original']['fit']
            elapsed, memory, training_ap = previous['training_seconds'], previous['memory'], previous['train_metrics']['average_precision']
            nodes = previous['complexity']['total_nodes']
            trees = previous['complexity']['trees']
        else:
            elapsed, memory, training_ap = fit['seconds'], fit, fit['train']['average_precision']
            nodes = verification['complexity'][name]['nodes']
            trees = verification['complexity'][name]['trees']
        final_ap = float(overall[(overall.variant == name) & (overall.rule == 'fixed_050')].average_precision.iloc[0])
        training_rows.append([NAMES[name], f'{elapsed:.1f}s', f'{memory["peak_rss"]/2**30:.2f}',
                              f'{memory["min_available_ram"]/2**30:.2f}', trees, f'{nodes:,}',
                              f'{training_ap:.6f}', f'{training_ap-final_ap:+.6f}'])
    scope = [row for state in history['states'].values() for row in state['rows']]
    scope_rows = [[split, f'{sum(r["rows"] for r in scope if r["split"]==split):,}',
                   *(f'{sum(r[col] for r in scope if r["split"]==split):,}' for col in
                     ('lag_120m_missing', 'lag_180m_missing', 'relative_growth_180m_missing'))]
                  for split in ('train', 'validation')]
    contrasts = []
    for original, improved in [('rf_original_state', 'rf_history_state'), ('rf_original_both', 'rf_history_both'),
                               ('xgb_original_state', 'xgb_history_state')]:
        a, b = picks[original], picks[improved]
        diff = np.array(b['fold_ap']) - a['fold_ap']
        old, new = (overall[(overall.variant == name) & overall.rule.eq('fixed_050')].iloc[0]
                    for name in (original, improved))
        contrasts.append([NAMES[improved], *(f'{value:+.6f}' for value in diff), f'{diff.mean():+.6f}',
                          f'{new.average_precision-old.average_precision:+.6f}',
                          f'{(new.average_precision/old.average_precision-1)*100:+.2f}%'])
    save('FEATURE_COMPARISON.md', f"""# Historical feature comparison

Spark {history['spark']} and Hadoop {history['hadoop']} read the five verified Silver state partitions, found the historical values within each county, and wrote a separate native Parquet dataset. The join retained every eligible anchor and its original label. State-trained comparisons use 1,053,328 training rows in 12 counties and all 582,532 2021 rows in 20 counties. The eight held-out counties were excluded from every fit. Their historical raw reports were used only to calculate their respective evaluation predictors.

| Predictor | Definition |
| --- | --- |
| 120-minute and 180-minute lags | Exact UTC offset. An absent report produces a missing value. |
| Three-hour change | Current outage count minus the exact 180-minute lag. |
| Rolling maximum | Largest observed count in the inclusive [t − 180 minutes, t] window. |
| Reporting coverage | Observed slots divided by 13, including the prediction anchor. |
| Recent trend | Current minus exact 30-minute lag, divided by 30 to represent customers per minute. |
| Relative growth | Three-hour change divided by the exact lag only when that lag is positive. |
| Four missingness flags | Mark unavailable 120-minute lag, 180-minute lag, 30-minute trend, and relative growth. |

{table(['Partition', 'Eligible rows', '120m lag missing', '180m lag missing', 'Relative growth missing'], scope_rows)}

A Spark range window uses timestamp values, so a missing report does not shift the lag to a neighboring slot. The interval ends at the prediction timestamp. Windows span UTC year boundaries within a county. For a positive current count, the original target requires all twelve future quarter-hour observations and an increase of at least the larger of 200 customers or 50% of the current count. Imputation learns a median per numeric feature in the training partition, and scaling learns that partition’s mean and standard deviation after imputation. Unseen geography produces a zero one-hot block and never gets a learned county or state effect of its own.

## Paired difference in average precision

{table(['History variant versus its original', '2018 H2 Δ', '2019 Δ', '2020 Δ', 'Mean OOF Δ', '2021 Δ', 'Relative 2021 Δ'], contrasts)}

Compare the paired differences across the same folds. Three temporal folds provide descriptive variation, and consecutive anchors can share an outage event and its future horizon. The differences do not establish independent-sample significance. The [model comparison](MODEL_COMPARISON.md) shows group-level results.
""")
    cv_rows = [[NAMES[name], str(info['depth'] or 12), *(f'{value:.6f}' for value in info['fold_ap']),
                f'{info["mean_ap"]:.6f}', f'{info["sd_ap"]:.6f}'] for name, info in picks.items()]
    search_rows = []
    for key in ('xgb_original_state', 'xgb_history_state'):
        for depth in (4, 6):
            rows = [r for r in selected['fold_search'] if r['name'] == key and r['depth'] == depth]
            search_rows.append([NAMES[key], depth, f'{np.mean([r["average_precision"] for r in rows]):.6f}',
                                f'{sum(r["seconds"] for r in rows):.1f}s'])
    every = overall[overall.rule.isin(['fixed_050', PRACTICAL, 'f2'])]
    geo = results[results.group.isin(['original', 'seen', 'unseen_county', 'unseen_state']) & results.rule.eq(PRACTICAL)]
    save('MODEL_COMPARISON.md', f"""# Random Forest versus XGBoost

The model selection criterion was mean average precision across 2018 H2, 2019, and 2020 with an expanding window and a strict three-hour horizon purge. Each model learned preprocessing and categorical encoders separately in each fold. Original Random Forest predictions and fit evidence were reused after exact key and label alignment. New classifiers were scored on those same observations. The locked 2021 prediction stage ran after the model ranking and cutoff selection.

## Chronological folds

{table(['Variant', 'Depth limit', '2018 H2 AP', '2019 AP', '2020 AP', 'Mean AP', 'Sample SD'], cv_rows)}

The fixed Random Forest has 100 trees, maximum depth 12, minimum leaf size 10, and seed 17. The CPU XGBoost search used two depth values, 120 histogram-based boosting rounds, learning rate 0.10, seed 17, and two threads. XGBoost builds each tree to improve the current ensemble and evaluates candidate splits in numeric bins. Its minimum child weight limits splits supported by too little loss curvature. The Random Forest averages independently fitted trees. No early stopping was used. These are bounded configurations on this laptop.

{table(['XGBoost candidate', 'Depth', 'Mean OOF AP', 'Sum of fit time'], search_rows)}

## Previously consulted 2021 development comparison

{table(['Variant', 'Decision rule', *SCORE_FIELDS], [[NAMES[r.variant], RULES[r.rule], *score_row(r)] for r in every.itertuples()])}

The operating candidate uses the highest-accuracy cutoff that attained at least 60% recall on pooled OOF. F2 is a more permissive comparison rule. Average precision summarizes the precision-recall ranking across all cutoffs. ROC-AUC measures how often positives outrank negatives. Group prevalence determines the AP of a constant score and is recorded beside group results.

## Geographic transfer at the operating candidate

{table(['Variant', 'Group', 'Rows', 'Prevalence', 'AP', 'Accuracy', 'Recall', 'Precision', 'FP / 1,000'],
        [[NAMES[r.variant], GROUPS[r.group], f'{r.rows:,}', pct(r.prevalence), f'{r.average_precision:.6f}',
          pct(r.accuracy), pct(r.recall), pct(r.precision), f'{r.false_alarms_per_1000:.1f}'] for r in geo.itertuples()])}

All 20 county metrics, all six operating cutoffs and confusion counts are in [metrics_2021.csv](model_results/metrics_2021.csv). Compare models within the same group because event prevalence and county mix change AP. New York is one unseen state. The geographic populations and 2021 have already been consulted during development.

## Runtime, memory, and generalization gap

{table(['Variant', 'Full fit time', 'Fit peak RSS GiB', 'Minimum available GiB', 'Trees', 'Nodes',
        'Training AP', 'Train minus 2021 AP'], training_rows)}

RSS is the sampled peak Python process working set. The archived forest used its original measurement, so process overhead differs. The fit includes imputation, scaling, geography encoding and estimator training. A training-versus-2021 gap combines overfitting with year and geographic composition changes. A fresh Python process reproduced {verification['reloaded_rows_per_model']} stored scores per new pipeline and verified {verification['protected_official_artifacts']} archived hashes for the official notebooks and artifacts.

## Use of hour_utc

{table(['Model', 'Hour rank', 'Hour AP drop', 'Largest AP drops'], [
        [NAMES[name], next(i for i, r in enumerate(rows, start=1) if r['feature'] == 'hour_utc'),
         f'{next(r["mean_ap_drop"] for r in rows if r["feature"] == "hour_utc"):+.6f}',
         ', '.join(f'{r["feature"]} {r["mean_ap_drop"]:+.4f}' for r in rows[:4])] for name, rows in permuted.items()])}

The same deterministic 20,000-row 2021 sample was scored with each numeric feature permuted three times. A drop in AP means the fitted model relied on that feature in the diagnostic. Correlation among historical features can spread measured importance across several columns. This is a post-selection association check.

![Average precision by geography](geographic_ap.png)

![Development-selected model confusion matrices](confusion_matrices.png)
""")
    rule_rows = results[results.variant.eq(chosen) & results.rule.eq(PRACTICAL) & results.group.isin(GROUPS)]
    xgb_pairs = [(name, picks[name]['mean_ap'] - picks[name.replace('xgb_', 'rf_')]['mean_ap'])
                 for name in picks if name.startswith('xgb_')]
    secondary = max(('rf_original_both', 'rf_history_both'), key=lambda name: picks[name]['mean_ap'])
    save('FINAL_RECOMMENDATION.md', f"""# Final recommendation

**Development candidate: {NAMES[chosen]}, cutoff {chosen_rule.threshold:.9f}.** It led the four primary State-only variants on mean chronological OOF AP ({picks[chosen]['mean_ap']:.6f}). The strongest secondary geography comparison, {NAMES[secondary]}, scored {picks[secondary]['mean_ap']:.6f} in those seen-county folds. The cutoff was selected by maximizing accuracy subject to at least 60% pooled OOF recall. Before deployment, confirm that this recall goal and the corresponding alert load suit the intended workflow.

{table(['2021 rule', *SCORE_FIELDS], [[RULES[r.rule], *score_row(r)] for r in overall[
       overall.variant.eq(chosen) & overall.rule.isin(['fixed_050', PRACTICAL, 'f2'])].itertuples()])}

The candidate’s 2021 AP changed by {chosen_rule.average_precision-base.average_precision:+.6f} against the original State forest, on the identical observations. At the proposed cutoff, recall is {pct(chosen_rule.recall)} with {chosen_rule.false_alarms_per_1000:.1f} false alarms per 1,000. Keeping cutoff 0.50 on that same candidate yields {pct(fixed.recall)} recall and {fixed.false_alarms_per_1000:.1f} false alarms per 1,000.

{table(['2021 population', 'Prevalence', 'AP', 'Recall', 'Precision', 'FP / 1,000'],
        [[GROUPS[r.group], pct(r.prevalence), f'{r.average_precision:.6f}', pct(r.recall), pct(r.precision),
          f'{r.false_alarms_per_1000:.1f}'] for r in rule_rows.itertuples()])}

The matched-feature XGBoost minus Random Forest mean OOF AP differences were {', '.join(f'{NAMES[name]} {delta:+.6f}' for name, delta in xgb_pairs)}. See [feature comparison](FEATURE_COMPARISON.md) for fold-specific changes from longer history and [model comparison](MODEL_COMPARISON.md) for all fixed and selected cutoffs.

Additional development counties remain worth investigating because four unseen-state counties from one state cannot establish nationwide transfer. Before a model freeze, agree on an operational false-alarm budget, evaluate across multiple leave-one-state-out development partitions and test whether contiguous alert consolidation is appropriate for the application. Any future freeze requires explicit approval. The official model was preserved and 2022 stayed sealed.
""")
    geography_plot(results)
    confusion_plot(results, chosen)


def geography_plot(results):
    primary = ['rf_original_state', 'rf_history_state', 'xgb_original_state', 'xgb_history_state']
    groups = ['all', 'seen', 'unseen_county', 'unseen_state']
    fig, ax = plt.subplots(figsize=(9.4, 5.0))
    x = np.arange(len(groups))
    width = .19
    for i, name in enumerate(primary):
        subset = results[results.variant.eq(name) & results.rule.eq(PRACTICAL)].set_index('group')
        ax.bar(x + (i-1.5)*width, subset.loc[groups].average_precision, width, label=NAMES[name])
    ax.set_xticks(x, [GROUPS[group] for group in groups])
    ax.set(ylabel='Average precision', title='2021 development ranking by geographic role')
    ax.legend(frameon=False, fontsize=8, ncols=2)
    ax.grid(axis='y', alpha=.25)
    figure(fig, 'geographic_ap.png')


def confusion_plot(results, chosen):
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5))
    for ax, rule in zip(axes, ('fixed_050', PRACTICAL, 'f2'), strict=True):
        row = results[(results.variant == chosen) & (results.group == 'all') & (results.rule == rule)].iloc[0]
        matrix = np.array([[row.tn, row.fp], [row.fn, row.tp]], dtype=int)
        ax.imshow(matrix / matrix.sum(axis=1, keepdims=True), cmap='Blues', vmin=0, vmax=1)
        for i, j in np.ndindex(2, 2):
            ax.text(j, i, f'{matrix[i,j]:,}', ha='center', va='center',
                    color='white' if matrix[i,j]/matrix[i].sum() > .5 else 'black')
        ax.set(xticks=[0, 1], yticks=[0, 1], xlabel='Predicted', ylabel='Observed',
               title=f'{RULES[rule]}\n{row.threshold:.6f}')
    fig.suptitle(f'{NAMES[chosen]} on identical 2021 rows')
    figure(fig, 'confusion_matrices.png')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('threshold', 'model'))
    if parser.parse_args().phase == 'threshold':
        threshold_report()
    else:
        model_reports()

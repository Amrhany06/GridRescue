"""Render AP comparisons from the experimental metrics table without refitting."""
import argparse

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from prepare_cohort import directories

COLORS = ['#344860', '#007D83', '#4265AC', '#A95136']
LABELS = ['Numeric', '+ State', '+ FIPS', '+ Both']
VARIANTS = ['numeric', 'state', 'fips', 'both']


def main(run_id):
    reports, _ = directories(run_id)
    output = reports / 'model_results'
    metrics = pd.read_csv(output / 'metrics.csv', dtype={'period': str})
    figure, axes = plt.subplots(2, 1, figsize=(10, 8), layout='constrained')
    cv = metrics[metrics.period.ne('2021') & metrics.group.eq('all')]
    trends = cv.pivot(index='period', columns='variant', values='average_precision')[VARIANTS]
    for variant, label, color in zip(VARIANTS, LABELS, COLORS):
        axes[0].plot(trends.index, trends[variant], label=label, color=color, marker='o')
    axes[0].set(title='Chronological cross-validation on the 12 training counties', ylabel='Average precision', ylim=(0, 1))
    axes[0].legend(ncols=4, loc='upper center')

    groups = {'original': 'Original 3', 'other_seen': 'Other seen', 'unseen_county': 'Unseen county',
              'unseen_state': 'Unseen state', 'all': 'All 20'}
    subset = metrics[metrics.period.eq('2021') & metrics.group.isin(groups)]
    figures = subset.pivot(index='group', columns='variant', values='average_precision').loc[list(groups), VARIANTS]
    figures.index = list(groups.values())
    figures.plot.bar(ax=axes[1], color=COLORS, rot=0)
    axes[1].set(title='2021 development AP on identical rows within each group', xlabel='', ylabel='Average precision', ylim=(0, 1))
    axes[1].legend(handles=axes[1].containers, labels=LABELS, ncols=4, loc='upper center')
    for axis in axes:
        axis.grid(axis='y', alpha=.2)
        axis.set_axisbelow(True)
    with (output / 'geographic_comparison.png').open('xb') as stream:
        figure.savefig(stream, dpi=160, format='png')
    plt.close(figure)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    main(parser.parse_args().run_id)

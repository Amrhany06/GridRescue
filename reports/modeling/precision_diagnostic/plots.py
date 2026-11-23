"""Render diagnostic plots from the exported measurements."""
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from diagnostic import ABLATION, CHAMPION, COLORS, MODELS, NAMES


def precision_recall(output):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex='col', layout='constrained')
    markers = {'target_40': 'o', 'target_50': 's', 'target_60': '^'}
    for row, (file, period, title) in enumerate((('oof', 'pooled_oof', '2018–2020 chronological OOF'),
                                                ('development', '2021', '2021 development'))):
        metrics = pd.read_csv(output / f'{file}_metrics.csv', dtype={'period': str}).query(
            'period == @period and group == "all"')
        for model in MODELS:
            curve = pd.read_parquet(output / f'pr_{file}_{model}.parquet')
            points = metrics[(metrics.model == model) & metrics.rule.isin(markers)]
            for col, ax in enumerate(axes[row]):
                ax.plot(curve.recall, curve.precision, color=COLORS[model], label=NAMES[model],
                        lw=1.6 if model == CHAMPION else 1.15, ls='--' if model == ABLATION else '-')
                for point in points.itertuples():
                    ax.scatter(point.recall, point.precision, color=COLORS[model], marker=markers[point.rule],
                               s=35 if col else 23, edgecolors='white', linewidths=.45, zorder=3)
        prevalence = metrics.prevalence.iloc[0]
        axes[row, 0].axhline(prevalence, ls=':', color='#444444', lw=1, label='Prevalence')
        for col, ax in enumerate(axes[row]):
            ax.set_title(f'{title} · {"full curve" if col == 0 else "operating range"}', fontsize=11)
            ax.xaxis.set_major_formatter(PercentFormatter(1))
            ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.grid(alpha=.2)
        axes[row, 0].set(xlim=(0, 1), ylim=(0, 1.02), ylabel='Precision')
        axes[row, 1].set(xlim=(.30, .66), ylim=(.22, .58))
    for ax in axes[-1]:
        ax.set_xlabel('Recall')
    axes[0, 0].legend(frameon=False, fontsize=8, loc='upper right')
    fig.suptitle('Precision–recall curves and OOF-selected points\n○ 40%   □ 50%   △ 60% OOF recall target', fontsize=13)
    fig.savefig(output / 'precision_recall.png', dpi=155)
    plt.close(fig)


def hour_patterns(output):
    metrics = pd.read_csv(output / 'hourly_metrics.csv', dtype={'fips_code': str})
    selected = metrics.query('period == "2021" and level == "all" and rule == "target_60"')
    a = selected[selected.model == CHAMPION]
    b = selected[selected.model == ABLATION]
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True, layout='constrained')
    axes[0].plot(a.hour_utc, a.prevalence, color='#343d53', marker='.', label='Positive prevalence')
    axes[0].bar(a.hour_utc, a.share_of_eligible_rows, color='#b6c4df', label='Share of eligible rows')
    for frame, model in ((a, CHAMPION), (b, ABLATION)):
        axes[1].plot(frame.hour_utc, frame.mean_score, color=COLORS[model], label=NAMES[model], marker='.')
        axes[2].plot(frame.hour_utc, frame.false_positive_rate, color=COLORS[model], label=NAMES[model], marker='.')
    for ax, label in zip(axes, ('Share of rows', 'Mean score', 'False-positive rate'), strict=True):
        ax.set_ylabel(label)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.grid(alpha=.2)
        ax.legend(frameon=False, fontsize=9)
    axes[-1].set(xlabel='UTC hour', xticks=range(24))
    fig.suptitle('2021 eligible observations by UTC hour · 60% OOF recall rules')
    fig.savefig(output / 'hour_patterns.png', dpi=155)
    plt.close(fig)

    county_hour = metrics.query('period == "2021" and level == "county" and rule == "incumbent"')
    ordering = county_hour[['state', 'fips_code']].drop_duplicates().sort_values(['state', 'fips_code'])
    counties = pd.read_csv(output / 'development_metrics.csv', dtype={'fips_code': str}).dropna(subset=['fips_code'])
    names = counties.drop_duplicates('fips_code').set_index('fips_code').county
    fig, axes = plt.subplots(1, 2, figsize=(12, 7), sharey=True, layout='constrained')
    for ax, field, title in zip(axes, ('prevalence', 'false_positive_rate'), ('Positive prevalence', 'False-positive rate'), strict=True):
        grid = county_hour.pivot(index='fips_code', columns='hour_utc', values=field).loc[ordering.fips_code]
        picture = ax.imshow(grid, aspect='auto', cmap='viridis', vmin=0, vmax=1)
        ax.set(title=title, xlabel='UTC hour', xticks=np.arange(0, 24, 3),
               yticks=range(len(ordering)), yticklabels=[f'{names[code]} ({code})' for code in ordering.fips_code])
        fig.colorbar(picture, ax=ax, format=PercentFormatter(1), shrink=.85)
    fig.suptitle('2021 hourly patterns by county · incumbent cutoff')
    fig.savefig(output / 'county_hour_heatmap.png', dpi=155)
    plt.close(fig)


def geographic_errors(output):
    data = pd.read_csv(output / 'development_metrics.csv', dtype={'fips_code': str}).dropna(subset=['county'])
    counties = data.query('model == @CHAMPION and rule == "incumbent"').sort_values('fp')
    colors = counties.role.map({'seen': '#214fa6', 'unseen_county': '#329282', 'unseen_state': '#a43a8a'})
    fig, axes = plt.subplots(1, 2, figsize=(10, 7), sharey=True, layout='constrained')
    y = np.arange(len(counties))
    axes[0].barh(y, counties.fp, color=colors)
    axes[1].barh(y, counties.false_alarms_per_1000, color=colors)
    axes[0].set(xlabel='False-positive rows', yticks=y,
                yticklabels=[f'{row.county} ({row.fips_code})' for row in counties.itertuples()])
    axes[1].set_xlabel('False positives per 1,000 eligible rows')
    for ax in axes:
        ax.grid(axis='x', alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle('2021 false-positive burden · incumbent XGBoost\nBlue = seen  ·  Green = unseen county  ·  Purple = unseen state')
    fig.savefig(output / 'geographic_false_positives.png', dpi=155)
    plt.close(fig)


def make_plots(output):
    precision_recall(output)
    hour_patterns(output)
    geographic_errors(output)

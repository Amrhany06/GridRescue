"""Generate bounded reference fixtures, exact fingerprints and inventory from trusted Windows artifacts."""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from cloud_core import YEARS, digest, load, save, verify_file
from cloud_data import COLUMNS, HERE, KEY, ROOT, SOURCE, fingerprint, read_rows, training_parity_sample
from cloud_train import FEATURE_INPUTS, preprocessing_snapshot, probability, record
from gridrescue.modeling import chronological_folds

PILOT_ID = 'pilot_20_20261121'
OLD_REPORT = HERE.parent / 'county_expansion' / PILOT_ID
OLD_DATA = ROOT / 'artifacts/modeling/county_expansion' / PILOT_ID
HISTORY = ROOT / 'artifacts/modeling/local_improvement/history'
OLD_RESULTS = HERE.parent / 'local_improvement/model_results'
BENCHMARK = 'xgb_history_state'


def storage_inventory():
    """Measure Parquet payload bytes only in explicitly development-scoped paths."""
    directories = {
        'native_sample_silver': ROOT / 'data/windows/silver/sample',
        'native_county_silver': ROOT / 'data/windows/silver/county',
        'native_sample_gold': ROOT / 'data/windows/gold/sample/features',
        'native_county_gold': ROOT / 'data/windows/gold/county/features',
        'native_county_label_audit': ROOT / 'data/windows/gold/county/label_audit',
        'pilot_bronze': OLD_DATA / 'bronze',
        'pilot_silver': OLD_DATA / 'silver',
        'pilot_labels': OLD_DATA / 'labels',
        'pilot_augmented_history': HISTORY,
    }
    sizes = {}
    for key, path in directories.items():
        if not path.is_dir():
            raise FileNotFoundError(path)
        if key == 'pilot_bronze':
            parts = [f for year in YEARS for f in (path / str(year)).glob('bucket=*/part-*.parquet')]
        elif key in ('pilot_labels', 'pilot_augmented_history'):
            splits = ('train', 'validation', 'purged') if key == 'pilot_labels' else ('train', 'validation')
            parts = [f for split in splits for f in path.glob(f's[0-9][0-9]/split={split}/part-*.parquet')]
        else:
            parts = list(path.glob('*.parquet')) if key.startswith('native_') else list(path.glob('s[0-9][0-9]/part-*.parquet'))
        sizes[key] = dict(path=path.relative_to(ROOT).as_posix(), files=len(parts),
                          bytes=sum(f.stat().st_size for f in parts),
                          rows=sum(pq.ParquetFile(f).metadata.num_rows for f in parts))
    raw_pins = load(HERE / 'source_manifest.json')['files']
    prior_source = load(OLD_REPORT / 'cohort.json')['inputs']
    source = []
    for pin, prior in zip(raw_pins, prior_source, strict=True):
        path = ROOT / 'data/raw' / pin['name']
        if (prior['year'], prior['bytes'], prior['sha256']) != (pin['year'], pin['size'], pin['sha256']):
            raise ValueError('Figshare pins disagree with the prior local source manifest')
        source.append(dict(year=pin['year'], path=path.relative_to(ROOT).as_posix(), **verify_file(path, pin)))
        print(f'Local {pin["year"]} matches Figshare MD5 and trusted SHA-256.', flush=True)
    archived = load(OLD_RESULTS / 'full_fits.json')
    protected = load(OLD_REPORT / 'model_results/configuration.json')['protected_hashes']
    official = {}
    for name, expected in protected.items():
        file = ROOT / name
        current = digest(file)
        if current != expected:
            raise ValueError(f'Protected file differs from archived digest: {name}')
        official[name] = dict(bytes=file.stat().st_size, sha256=current)
    models = {}
    for variant, metrics in archived.items():
        if 'sha256' in metrics:
            model = ROOT / f'artifacts/modeling/local_improvement/models/{variant}.joblib'
            current = digest(model)
            if current != metrics['sha256']:
                raise ValueError(f'Experimental model changed: {model}')
            models[variant] = dict(bytes=model.stat().st_size, sha256=current)
    return dict(measured_utc=datetime.now(timezone.utc).isoformat(), raw=source, parquet=sizes,
                protected=official, experimental_models=models, available_local_disk_bytes=shutil.disk_usage(ROOT).free)


def pilot_paths(split):
    return sorted(HISTORY.glob(f's[0-9][0-9]/split={split}'))


def reference_manifest(cohort):
    subsets = {name: read_rows(pilot_paths(name), columns=KEY) for name in ('train', 'validation')}
    archived = pd.read_parquet(OLD_RESULTS / 'predictions_2021.parquet', columns=KEY)
    if fingerprint(archived) != fingerprint(subsets['validation']):
        raise ValueError('Trusted feature and champion 2021 labels or keys disagree')
    result = {name: dict(overall=fingerprint(frame), by_county={code: fingerprint(rows) for code, rows in
                      frame.groupby('fips_code', observed=True)}) for name, frame in subsets.items()}
    result['counties'] = [{key: row[key] for key in ('fips_code', 'state', 'county', 'role', 'original')} for row in cohort]
    result['folds'] = {}
    train = subsets['train']
    for fold in chronological_folds(train):
        name = fold['name']
        result['folds'][name] = {part: fingerprint(train.iloc[fold[part]]) for part in ('train', 'validation')}
        baseline = pd.read_parquet(OLD_RESULTS / f'oof_{BENCHMARK}_depth6_{name}.parquet', columns=KEY)
        if fingerprint(baseline) != result['folds'][name]['validation']:
            raise ValueError(f'Trusted fold OOF scores disagree with feature labels for {name}')
    return result


def tier_a_parity_reference():
    """Build a small Tier A gate from protected local features, scores and fitted preprocessing."""
    evidence = load(HERE.parent / 'precision_diagnostic/results/run_evidence.json')['input_sha256']
    history = ROOT / 'artifacts/modeling/local_improvement'
    model_path = history / 'models' / f'{BENCHMARK}.joblib'
    prediction_path = OLD_RESULTS / 'predictions_2021.parquet'
    sources = {}
    features = {}

    def verify(path):
        relative = path.relative_to(ROOT).as_posix()
        actual = digest(path)
        if actual != evidence[relative]:
            raise ValueError(f'Tier A reference source changed: {relative}')
        sources[relative] = actual

    for split in ('train', 'validation'):
        paths = pilot_paths(split)
        for directory in paths:
            for path in sorted(directory.glob('part-*.parquet')):
                verify(path)
        features[split] = training_parity_sample(read_rows(paths))
    verify(model_path)
    verify(prediction_path)
    sys.path.insert(0, str(history / 'deps_local'))
    model = joblib.load(model_path)
    sample = features['validation']
    saved = pd.read_parquet(prediction_path, columns=[*KEY, BENCHMARK])
    scores = sample[KEY].merge(saved, on=KEY, validate='one_to_one')[BENCHMARK].astype(float).to_numpy()
    np.testing.assert_array_equal(probability(model, sample[FEATURE_INPUTS]), scores)
    roles = pd.DataFrame(load(HERE / 'reference_manifest.json')['counties'])
    geography = saved.fips_code.map(roles.set_index('fips_code').state)
    cutoff = load(HERE / 'experiment_manifest.json')['benchmark']['threshold']
    state_metrics = {}
    for state, group in saved.groupby(geography, observed=True):
        metrics = record(group.candidate_y, group[BENCHMARK], cutoff)
        state_metrics[f'state_{state}'] = {key: float(metrics[key]) for key in (
            'average_precision', 'recall', 'precision', 'accuracy', 'false_alarms_per_1000')}
    return {'source_sha256': sources,
            'features': {split: frame.assign(timestamp=frame.timestamp.dt.strftime('%Y-%m-%dT%H:%M:%SZ'))
                         .astype(object).where(frame.notna(), None).to_dict('records')
                         for split, frame in features.items()},
            'preprocessing': preprocessing_snapshot(model, sample), 'scores': scores.tolist(),
            'state_metrics': state_metrics}


def fixture_reference(cohort, output):
    """Export overlapping-safe raw context for deterministic trusted feature anchors."""
    anchors = []
    for split in ('train', 'validation'):
        codes = [row['fips_code'] for row in cohort if split == 'validation' or row['role'] == 'seen']
        for code in codes:
            paths = [path for path in pilot_paths(split) if path.parent.name == f's{code[:2]}']
            frame = read_rows(paths, [code], COLUMNS)
            pos = frame.loc[frame.candidate_y.eq(1) & frame.lag_180m.notna()]
            neg = frame.loc[frame.candidate_y.eq(0) & frame.lag_180m.isna()]
            if neg.empty:
                neg = frame.loc[frame.candidate_y.eq(0)]
            for subset in (pos, neg):
                if not subset.empty:
                    anchors.append(subset.iloc[[len(subset) // 2]].assign(split=split))
            if split == 'validation':
                first = frame.loc[frame.timestamp < pd.Timestamp('2021-01-01T03:00:00Z')]
                if not first.empty:
                    anchors.append(first.iloc[:1].assign(split=split))
    expected = pd.concat(anchors, ignore_index=True).drop_duplicates(KEY[:2]).sort_values(KEY[:2])
    expected['timestamp'] = expected.timestamp.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    expected.to_json(output / 'fixture_rows.tmp', orient='records', double_precision=15)
    rows = load(output / 'fixture_rows.tmp')
    (output / 'fixture_rows.tmp').unlink()
    save(output / 'fixture_expected.json', {'rows': rows})

    raw = []
    half = pd.DateOffset(hours=3)
    for year in YEARS:
        for state in sorted({row['fips_code'][:2] for row in cohort}):
            conditions = []
            for item in expected.loc[expected.fips_code.str.startswith(state)].itertuples():
                anchor = pd.Timestamp(item.timestamp)
                lo, hi = anchor - half, anchor + half
                if hi.year < year or lo.year > year:
                    continue
                conditions.append([('fips_code', '=', item.fips_code),
                                   ('run_start_time', '>=', lo.strftime('%Y-%m-%d %H:%M:%S')),
                                   ('run_start_time', '<=', hi.strftime('%Y-%m-%d %H:%M:%S'))])
            if conditions:
                parts = sorted((OLD_DATA / 'bronze' / str(year) / f'bucket=s{state}').glob('part-*.parquet'))
                raw.append(pd.read_parquet(parts, columns=SOURCE, filters=conditions))
    pd.concat(raw, ignore_index=True).to_csv(output / 'fixture_bronze.csv', index=False, lineterminator='\n')
    print(f'Wrote {len(expected)} trusted feature anchors using {sum(map(len, raw))} archived Bronze rows.', flush=True)


def main(output, skip_inventory):
    output.mkdir(parents=True, exist_ok=True)
    cohort = load(OLD_REPORT / 'cohort.json')['county_selection']
    save(output / 'reference_manifest.json', reference_manifest(cohort))
    fixture_reference(cohort, output)
    if not skip_inventory:
        save(output / 'local_storage_audit.json', storage_inventory())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--skip-inventory', action='store_true')
    parser.add_argument('--tier-a-parity-only', action='store_true')
    args = parser.parse_args()
    if args.tier_a_parity_only:
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / 'tier_a_parity_reference.json').open('x', encoding='utf-8') as stream:
            json.dump(tier_a_parity_reference(), stream, separators=(',', ':'), sort_keys=True, allow_nan=False)
    else:
        main(args.output, args.skip_inventory)

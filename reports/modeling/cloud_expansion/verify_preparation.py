"""Independent bounded recheck of the notebook, windows, and protected artifacts."""
import argparse
import ast
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import nbformat
import pandas as pd

from cloud_core import YEARS, digest, load
from cloud_data import HERE, KEY, ROOT, fingerprint, read_rows, verify_features
from cloud_run import PACKAGE_FILES
from cloud_train import Training, fold_bounds, recall_cutoffs
from prepare_local import OLD_RESULTS, pilot_paths, tier_a_parity_reference


def verify_notebook():
    path = ROOT / 'notebooks/colab_gridrescue_large_scale.ipynb'
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    checked, gated = 0, 0
    for i, cell in enumerate(notebook.cells):
        if cell.cell_type != 'code':
            continue
        if cell.execution_count is not None or cell.outputs:
            raise ValueError('Notebook must be delivered unexecuted')
        compiled = compile(cell.source, f'notebook-cell-{i}', 'exec')
        checked += 1
        if 'RUN_' in cell.source or 'EXPORT_TIERS = ' in cell.source:
            exec(compiled, {'stage': lambda *_: (_ for _ in ()).throw(ValueError('Default branch started a stage'))})
            gated += 1
        if 'BUNDLE_B64 =' in cell.source:
            values = {stmt.targets[0].id: ast.literal_eval(stmt.value) for stmt in ast.parse(cell.source).body
                      if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)
                      and stmt.targets[0].id in {'BUNDLE_B64', 'BUNDLE_SHA'}}
            bundle = base64.b64decode(values['BUNDLE_B64'], validate=True)
            if hashlib.sha256(bundle).hexdigest() != values['BUNDLE_SHA']:
                raise ValueError('Embedded code ZIP has changed')
            with ZipFile(BytesIO(bundle)) as zipped:
                if tuple(zipped.namelist()) != PACKAGE_FILES:
                    raise ValueError('The bundle contains unexpected files')
                for name in zipped.namelist():
                    if zipped.read(name) != (ROOT / name).read_bytes():
                        raise ValueError(f'Stale notebook content: {name}')
    if (checked, gated) != (13, 7):
        raise ValueError('Unexpected cell coverage')
    return {'code_cells_compiled': checked, 'safe_default_cells_executed': gated, 'embedded_files_checked': len(PACKAGE_FILES),
            'notebook_bytes': path.stat().st_size, 'bundle_bytes': len(bundle)}


def verify_development(spec, reference):
    Training(None, spec)  # Validate the selected feature/config contract without a fit.
    held_in = sorted(row['fips_code'] for row in reference['counties'] if row['role'] == 'seen')
    predictions = []
    for name, *_ in spec['folds']:
        _, start, _, train_end, val_end = fold_bounds(spec['folds'], name)
        for part, lo, hi in (('train', None, train_end), ('validation', start, val_end)):
            sample = read_rows(pilot_paths('train'), held_in, KEY, lo, hi)
            if fingerprint(sample) != reference['folds'][name][part]:
                raise ValueError(f'Cloud Arrow bounds differ from the trusted archived fold {name}/{part}')
        predictions.append(pd.read_parquet(OLD_RESULTS / f'oof_xgb_history_state_depth6_{name}.parquet'))
    scores = pd.concat(predictions, ignore_index=True)
    thresholds = recall_cutoffs(scores.candidate_y, scores.score, spec['recall_targets'])
    earlier = load(HERE.parent / 'precision_diagnostic/results/frozen_thresholds.json')['models']['xgb_history_state']
    if any(earlier[rule] != value for rule, value in thresholds.items()):
        raise ValueError('Cloud OOF threshold calculation differs from the precision diagnostic')

    fixture = pd.DataFrame(load(HERE / 'fixture_expected.json')['rows'])
    fixture['timestamp'] = pd.to_datetime(fixture.timestamp, utc=True).astype('datetime64[ns, UTC]')
    for split in ('train', 'validation'):
        sample = fixture.loc[fixture.split.eq(split)]
        actual = read_rows(pilot_paths(split), sorted(sample.fips_code.unique()), timestamps=sample.timestamp.unique())
        actual = actual.merge(sample[KEY[:2]], on=KEY[:2], validate='one_to_one')
        verify_features(actual.assign(split=split), sample)
    return {'arrow_fold_partitions_exact': 2 * len(spec['folds']), 'oof_rows_checked': len(scores),
            'oof_cutoffs_exact': thresholds, 'archived_feature_sample_checked': len(fixture),
            'feature_count': len(spec['features']), 'training_rows': reference['train']['overall']['rows'],
            'development_rows': reference['validation']['overall']['rows']}


def main(output):
    inventory = load(HERE / 'local_storage_audit.json')
    for file, pin in inventory['protected'].items():
        if digest(ROOT / file) != pin['sha256']:
            raise ValueError(f'Protected file changed: {file}')
    for variant, pin in inventory['experimental_models'].items():
        if digest(ROOT / f'artifacts/modeling/local_improvement/models/{variant}.joblib') != pin['sha256']:
            raise ValueError(f'Experimental model changed: {variant}')
    pins = load(HERE / 'source_manifest.json')['files']
    if tuple(record['year'] for record in inventory['raw']) != YEARS:
        raise ValueError('Unexpected raw years in local audit')
    for pin, real in zip(pins, inventory['raw'], strict=True):
        if any(pin[key] != real[key] for key in ('year', 'size', 'md5', 'sha256')):
            raise ValueError('Local digest does not match the pinned development source')
    notebook = verify_notebook()
    development = verify_development(load(HERE / 'experiment_manifest.json'), load(HERE / 'reference_manifest.json'))
    parity = tier_a_parity_reference()
    if parity != load(HERE / 'tier_a_parity_reference.json'):
        raise ValueError('Tier A parity reference differs from the protected Windows replay')
    development['tier_a_parity_feature_rows'] = {name: len(rows) for name, rows in parity['features'].items()}
    development['tier_a_preprocessing_and_saved_score_reload_rows'] = len(parity['scores'])
    evidence = dict(status='PASS', scope='local preparation; fixtures and archived predictions only', notebook=notebook,
                    development=development, protected_files=len(inventory['protected']),
                    experimental_models=len(inventory['experimental_models']), checksum_matched_years=list(YEARS),
                    cloud_fit_executed=False, nationwide_download_executed=False)
    if output is not None:
        with output.open('x', encoding='utf-8') as stream:
            json.dump(evidence, stream, indent=2, allow_nan=False)
    print(evidence)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    main(**vars(parser.parse_args()))

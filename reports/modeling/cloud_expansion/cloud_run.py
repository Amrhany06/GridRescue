"""Entry point for one explicitly enabled development-only Colab stage."""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

from cloud_core import (YEARS, digest, download_file, fetch_metadata, gpu_details, load, require_resources,
                        resources, save)
from cloud_data import Datasets, HERE, ROOT, spark_session, verify_fixture
from cloud_train import Training, training_budget

PACKAGE_FILES = (
    'src/gridrescue/__init__.py', 'src/gridrescue/pipeline.py', 'src/gridrescue/experiment.py',
    'src/gridrescue/modeling.py', 'src/gridrescue/storage.py',
    'reports/modeling/county_expansion/prepare_cohort.py', 'reports/modeling/county_expansion/train_cohort.py',
    'reports/modeling/local_improvement/history.py', 'reports/modeling/local_improvement/thresholds.py',
    'reports/modeling/local_improvement/train_local.py',
    *('reports/modeling/cloud_expansion/' + name for name in (
        'cloud_core.py', 'cloud_data.py', 'cloud_train.py', 'cloud_run.py', 'source_manifest.json',
        'experiment_manifest.json', 'reference_manifest.json', 'fixture_expected.json', 'fixture_bronze.csv',
        'tier_a_parity_reference.json', 'requirements-colab.txt', 'test_cloud.py', 'test_cloud_spark.py')),
)


def pinned_versions():
    return dict(line.split('==') for line in (HERE / 'requirements-colab.txt').read_text(encoding='utf-8').splitlines() if line)


def runtime_environment():
    installed = {name: version(name) for name in pinned_versions()}
    if installed != pinned_versions() or sys.version_info[:2] != (3, 12):
        raise RuntimeError(f'Use the notebook’s isolated Python 3.12 dependencies. Loaded {installed} on {sys.version}.')
    java = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True, timeout=10).splitlines()[0]
    if not re.search(r'version "17(?:\.|\")', java):
        raise RuntimeError(f'Java 17 is required for this Spark profile. Found {java}.')
    return {'python': platform.python_version(), 'packages': installed, 'system': platform.system(),
            'processor': platform.machine(), 'java': java, 'xgboost_device': 'cpu'}


def config(pins, vm, drive):
    runtime = runtime_environment()
    compatibility = {key: runtime[key] for key in ('packages', 'system', 'processor', 'xgboost_device')}
    compatibility.update(python_minor='3.12', java_major=17)
    signature = {'files': {name: digest(ROOT / name) for name in PACKAGE_FILES}, 'environment': compatibility}
    identity = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    run_name = f'figshare-v{pins["version"]}-{identity[:16]}'
    remote = drive / run_name
    remote.mkdir(parents=True, exist_ok=True)
    recipe = remote / 'run_manifest.json'
    if recipe.exists():
        if load(recipe)['signature'] != signature:
            raise ValueError('Existing Drive run uses a different source, program or runtime. Use its matching notebook.')
    else:
        tmp = recipe.with_suffix('.json.partial')
        save(tmp, {'signature': signature, 'initial_runtime_details': runtime})
        os.replace(tmp, recipe)
    pin_map = {row['year']: row for row in pins['files']}
    raw = drive / f'figshare-{pins["article_id"]}-v{pins["version"]}'
    data = Datasets(vm / run_name / 'stages', remote / 'checkpoints', raw, pin_map,
                    load(HERE / 'reference_manifest.json'))
    print(f'Run identity: {run_name}\nDrive: {remote}', flush=True)
    return data, remote


def run(stage, vm, drive, execute, tier, tiers):
    vm.mkdir(parents=True, exist_ok=True)
    pins = load(HERE / 'source_manifest.json')
    if stage == 'diagnostics':
        print(json.dumps({**resources(vm), 'python': platform.python_version(), 'GPU': gpu_details()}, indent=2))
        return
    if stage == 'metadata':
        print(json.dumps(fetch_metadata(pins), indent=2))
        return
    if stage in ('download', 'pilot', 'expand', 'train') and not execute:
        raise RuntimeError(f'{stage} is intentionally disabled. Turn on its notebook switch to start it.')
    data, remote = config(pins, vm, drive)
    spec = load(HERE / 'experiment_manifest.json')
    if stage == 'status':
        print(json.dumps({'git_or_notebook_signature': remote.name, 'storage': resources(vm),
                          'published_checkpoints': sorted(p.name for p in data.drive.glob('*.zip'))}, indent=2))
        return
    if stage == 'download':
        data.stage('sample-equivalence')
        selected = fetch_metadata(pins)
        for year in YEARS:
            info = selected[year]
            print(f'Checking {info["name"]} ({info["size"]:,} bytes) in cloud storage.', flush=True)
            verified = download_file(info['download_url'], data.raw_drive / info['name'], info)
            print(json.dumps({'year': year, **verified}), flush=True)
        return
    if stage in ('fixture', 'pilot', 'expand'):
        if stage == 'fixture' and ((data.drive / 'sample-equivalence.zip').exists()):
            print(load(data.stage('sample-equivalence') / 'fixture.json'))
            return
        if stage != 'fixture':
            data.stage('sample-equivalence')
            completion = 'pilot-verified' if stage == 'pilot' else 'expansion-verified'
            if (data.drive / f'{completion}.zip').exists():
                print(load(data.stage(completion) / 'dataset.json'))
                return
        require_resources(vm, 3 if stage == 'fixture' else 7, 2 if stage == 'fixture' else 15, stage)
        spark = spark_session(vm / 'spark_scratch', '2g' if stage == 'fixture' else '4g', 2 if stage == 'fixture' else 4)
        try:
            if stage == 'fixture':
                def sample(out):
                    save(out / 'fixture.json', verify_fixture(spark))
                print(load(data.stage('sample-equivalence', sample) / 'fixture.json'))
            elif stage == 'pilot':
                print(load(data.baseline(spark) / 'dataset.json'))
            else:
                data.stage('tier-A-parity')
                result = load(data.expanded(spark, spec['expansion']['max_candidates']) / 'dataset.json')
                for name, plan in result['tiers'].items():
                    ram = training_budget(plan['rows'], len(spec['features']) + len(plan['states']))
                    print(f'Tier {name}: {plan["rows"]:,} eligible rows, {len(plan["counties"])} counties, '
                          f'{len(plan["states"])} states; fit gate {ram:.2f} GiB available RAM.', flush=True)
        finally:
            spark.stop()
        return
    training = Training(data, spec)
    if stage == 'train':
        training.train(tier)
        print(f'Tier {tier} model and OOF thresholds checkpointed. Run its evaluation cell.')
    elif stage == 'evaluate':
        result = training.evaluate(tier)
        print(f'Evaluation checkpoint: {result}')
    elif stage == 'export':
        stage_id = 'comparison-' + '-'.join(tiers)
        result = data.stage(stage_id, lambda out: training.export(tiers, out))
        print(f'Download this compact report archive from Drive: {data.drive / (stage_id + ".zip")}')
        print(f'Unpacked comparison in this VM: {result}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['diagnostics', 'metadata', 'fixture', 'download', 'pilot', 'expand',
                                          'status', 'train', 'evaluate', 'export'])
    parser.add_argument('--vm', type=Path, required=True)
    parser.add_argument('--drive', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--tier', choices=['A', 'B', 'C'], default='A')
    parser.add_argument('--tiers', nargs='+', choices=['A', 'B', 'C'], default=['A'])
    args = parser.parse_args()
    if len(args.tiers) != len(set(args.tiers)):
        parser.error('Use each comparison tier once')
    run(**vars(args))

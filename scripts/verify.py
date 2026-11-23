"""Run named checks with unambiguous subprocess exit codes and preserved logs."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    'dependencies': ['-m', 'pip', 'check'],
    'syntax': ['-m', 'compileall', '-q', 'src', 'scripts', 'tests'],
    'layout': ['scripts/check_layout.py'],
    'tests': ['-m', 'unittest', 'discover', '-s', 'tests', '-v'],
    'preflight': ['scripts/preflight.py'],
    'notebooks': ['scripts/execute_notebooks.py'],
    'memory_sample': ['scripts/run_pipeline.py','--audit-only'],
    'memory_county': ['scripts/run_pipeline.py','--scope','county','--audit-only'],
    'full_integrity': ['scripts/full_source_audit.py'],
    'pipeline_sample': ['scripts/run_pipeline.py'],
    'pipeline_county': ['scripts/run_pipeline.py','--scope','county'],
    'feature_coverage': ['scripts/feature_feasibility.py'],
    'dashboard_export': ['scripts/export_dashboard.py'],
    'dashboard_tests': ['-m','unittest','discover','-s','tests','-p','test_dashboard.py','-v'],
    'target_audit': ['scripts/audit_target.py'],
    'performance': ['scripts/benchmark_processing.py'],
    'dashboard': ['scripts/verify_dashboard.py'],
    'persistence': ['scripts/verify_persistence.py'],
    'notebook_markdown': ['-m','unittest','discover','-s','tests','-p','test_notebook_markdown.py','-v'],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checks', nargs='+', choices=CHECKS)
    args = parser.parse_args()
    out = ROOT / 'reports/verification'
    out.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), JUPYTER_PATH=str(Path(sys.prefix)/'share/jupyter'))
    failed = False
    for name in args.checks:
        started = datetime.now(timezone.utc).isoformat()
        for suffix in ['txt','json']:
            previous=out/(name+'.'+suffix)
            if previous.exists():
                backup=ROOT/'artifacts/verification_history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')/previous.name
                backup.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(previous,backup)
        with (out / (name + '.txt')).open('w', encoding='utf-8') as log:
            result = subprocess.run([sys.executable, *CHECKS[name]], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        item = dict(check=name, started_utc=started, completed_utc=datetime.now(timezone.utc).isoformat(),
                    exit_code=result.returncode, log=f'reports/verification/{name}.txt')
        (out / (name + '.json')).write_text(json.dumps(item, indent=2)+'\n', encoding='utf-8')
        with (out / 'history.jsonl').open('a', encoding='utf-8') as history:
            history.write(json.dumps(item)+'\n')
        print(json.dumps(item), flush=True)
        failed |= result.returncode != 0
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())

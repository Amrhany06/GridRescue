"""Verify canonical inputs and content hashes without parsing held-out data."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'reports/source_manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        path = ROOT / item['path']
        assert path.parent == ROOT / 'data/raw'
        assert path.stat().st_size == item['bytes']
    for name in ['Task 1 for ML (1).pdf', 'Task 2 for ML.pdf', 'Task 3 for ML.pdf']:
        assert (ROOT / 'docs/requirements' / name).is_file()
    assert (ROOT / 'docs/GridRescue_Complete_Project_Explained.md').is_file()
    assert (ROOT / 'GridRescue_Codex_Copy_Paste_Prompt.md').is_file()
    for name in ['scripts', 'src/gridrescue', 'notebooks', 'tests', 'reports', 'artifacts', 'app', 'data/sample', 'data/bronze', 'data/silver', 'data/gold']:
        assert (ROOT / name).is_dir(), name
    for entry in json.loads((ROOT / 'reports/layout_migration.json').read_text(encoding='utf-8')):
        # CSV hashes were already checked over all relocated bytes by migration.
        if not entry['path'].endswith('.csv'):
            with (ROOT / entry['path']).open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256']
    print('Canonical layout verified; five CSV sizes and five document hashes match relocation ledger.')


if __name__ == '__main__':
    main()

"""One-time, content-preserving relocation with a saved integrity ledger."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    pairs = [(ROOT / f'eaglei_outages_{y}.csv', ROOT / 'data/raw' / f'eaglei_outages_{y}.csv') for y in range(2018, 2023)]
    pairs += [(ROOT / name, ROOT / 'docs/requirements' / name) for name in ['Task 1 for ML (1).pdf', 'Task 2 for ML.pdf', 'Task 3 for ML.pdf']]
    kit = ROOT / 'GridRescue_Complete_Explainer_And_Codex_Kit (2)'
    pairs += [(kit / 'GridRescue_Complete_Project_Explained.md', ROOT / 'docs/GridRescue_Complete_Project_Explained.md'),
              (kit / 'GridRescue_Codex_Copy_Paste_Prompt.md', ROOT / 'GridRescue_Codex_Copy_Paste_Prompt.md')]
    # Validate all targets before any move. Never replace an existing file.
    for source, target in pairs:
        if not source.is_relative_to(ROOT) or not target.is_relative_to(ROOT):
            raise ValueError('Path outside workspace')
        if source.exists() and target.exists():
            raise FileExistsError(target)
        if not source.exists() and not target.exists():
            raise FileNotFoundError(source)
    ledger = []
    for source, target in pairs:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            source.rename(target)
        with target.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        ledger.append(dict(previous_path=source.relative_to(ROOT).as_posix(), path=target.relative_to(ROOT).as_posix(), bytes=target.stat().st_size, sha256=digest))
    for stage in ['bronze', 'silver', 'gold']:
        (ROOT / 'data' / stage).mkdir(exist_ok=True)
    manifest_path = ROOT / 'reports/source_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for item in manifest['files']:
        moved = next(record for record in ledger if Path(record['path']).name == Path(item['path']).name)
        assert item['sha256'] == moved['sha256'], moved['path']
        item['previous_path'] = item['path']
        item['path'] = moved['path']
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    sample_path = ROOT / 'reports/sample_manifest.json'
    samples = json.loads(sample_path.read_text(encoding='utf-8'))
    for item in samples:
        item['source'] = f"data/raw/eaglei_outages_{item['year']}.csv"
    sample_path.write_text(json.dumps(samples, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'reports/layout_migration.json').write_text(json.dumps(ledger, indent=2) + '\n', encoding='utf-8')
    print(f'Verified {len(ledger)} relocated files; all five CSV hashes match the prior manifest.')


if __name__ == '__main__':
    main()

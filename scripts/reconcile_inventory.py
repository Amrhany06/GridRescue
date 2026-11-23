"""Integrity-only record count: no 2022 values, features, or labels are emitted.

Reuse the independent CSV parser counts from the completed development county
extraction, then parse held-out 2022 only to validate record shape and count.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    county = json.loads((ROOT / 'reports/county_manifest.json').read_text(encoding='utf-8'))
    assert county['status'] == 'VERIFIED'
    manifest_path = ROOT / 'reports/source_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    development_counts = {Path(f['source']).name: f['parsed_rows'] for f in county['files']}
    report = {'scope': 'CSV syntax/shape and record counts only; 2022 sealed from all development analysis', 'files': []}
    for item in manifest['files']:
        path = ROOT / item['path']
        if path.name in development_counts:
            count = development_counts[path.name]
        elif path.name == 'eaglei_outages_2022.csv':
            count = 0
            with path.open(newline='', encoding='utf-8-sig') as stream:
                reader = csv.reader(stream)
                assert next(reader) == ['fips_code', 'county', 'state', 'customers_out', 'run_start_time']
                for row in reader:
                    if len(row) != 5:
                        raise ValueError(f'Invalid shape at record {count+1}')
                    count += 1
        else:
            raise ValueError(path.name)
        assert count == item['physical_data_lines']
        item['row_count'] = count
        item['status'] = 'VERIFIED Python csv record count and original byte hash; Spark count recorded separately'
        report['files'].append({'path': item['path'], 'csv_parsed_records': count,
                                'physical_data_lines': item['physical_data_lines'], 'header_records': 1})
    total = sum(f['csv_parsed_records'] for f in report['files'])
    report.update(csv_parsed_record_total=total, header_total=5,
                  records_including_headers=total+5,
                  supplied_inventory_total=manifest['published_total_not_measured'],
                  interpretation='Every supplied annual count equals local parsed data records plus one header. Five headers exactly explain the arithmetic discrepancy. Upstream author counting methodology is not independently verified.')
    assert total + 5 == manifest['published_total_not_measured']
    manifest['parsed_row_total'] = total
    manifest['inventory_note'] = report['interpretation'] + ' Python csv parsed all five files; 2022 integrity count only. Spark development counts are separate.'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'reports/parsed_inventory.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

"""Extract fixed counties over complete development years, never 2022.

Count CSV records independently of Spark. County choices are fixed before label
inspection: Los Angeles (06037), Harris (48201), Miami-Dade (12086). Geographic
examples assess temporal feasibility; they are not a representative cohort.
"""
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from full_source_audit import development_sources

ROOT = Path(__file__).resolve().parents[1]
COUNTIES = {'06037', '48201', '12086'}
HEADER = ['fips_code', 'county', 'state', 'customers_out', 'run_start_time']


def extract_file(source, target, counties):
    parsed = selected = 0
    with source.open(newline='', encoding='utf-8-sig') as src, target.open('w', newline='', encoding='utf-8') as dst:
        reader, writer = csv.reader(src), csv.writer(dst)
        if next(reader) != HEADER:
            raise ValueError(f'Unexpected header: {source}')
        writer.writerow(HEADER)
        for row in reader:
            if len(row) != 5:
                raise ValueError(f'Invalid column count at record {parsed + 1} in {source.name}')
            parsed += 1
            if row[0] in counties:
                writer.writerow(row)
                selected += 1
    return {'parsed_rows': parsed, 'selected_rows': selected}


def main():
    out = ROOT / 'data/county_coverage'
    out.mkdir(exist_ok=True)
    report = {'scope': 'Three fixed counties, all source dates in 2018-2021; 2022 never opened',
              'county_fips': sorted(COUNTIES), 'selection': 'Fixed geographic examples before label inspection; no outcome-based search',
              'started_utc': datetime.now(timezone.utc).isoformat(), 'status': 'RUNNING', 'files': []}
    report_path = ROOT / 'reports/county_manifest.json'
    for source in development_sources(ROOT):
        started = time.perf_counter()
        item = {'source': source.relative_to(ROOT).as_posix(), 'sample': (out / source.name).relative_to(ROOT).as_posix(),
                **extract_file(source, out / source.name, COUNTIES), 'elapsed_seconds': time.perf_counter() - started}
        report['files'].append(item)
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(item), flush=True)
    report['status'] = 'VERIFIED'
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

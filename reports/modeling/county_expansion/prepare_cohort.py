"""Qualify, extract, and build the isolated 2018–2021 experiment cohort."""
import argparse
from calendar import monthrange
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from gridrescue.pipeline import make_spark, read_source
from gridrescue.pipeline import PREDICTORS, audit_labels, clean, features
from gridrescue.storage import sha256
from pyspark.sql import functions as F

YEARS = (2018, 2019, 2020, 2021)
STATE_ORDER = {'California': '06', 'Florida': '12', 'Texas': '48', 'Illinois': '17', 'New York': '36',
               'Pennsylvania': '42', 'Ohio': '39', 'North Carolina': '37', 'Washington': '53'}
ORIGINAL = {'California': '06037', 'Florida': '12086', 'Texas': '48201'}
ANNUAL_MINIMUM = 0.90
MONTH_MINIMUM = 0.80
COVERAGE_TIERS = ((ANNUAL_MINIMUM, MONTH_MINIMUM), (.75, .50), (.65, .40), (.55, .30), (.50, .25))


def write_new(path, value):
    """Create a new report without replacing a previous run's evidence."""
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, default=str, allow_nan=False)
        stream.write('\n')


def directories(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,45}', run_id):
        raise ValueError('Run ID must contain only letters, numbers, hyphens, or underscores')
    return HERE / run_id, ROOT / 'artifacts/modeling/county_expansion' / run_id


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def qualify_counties(rows, annual_minimum=ANNUAL_MINIMUM, month_minimum=MONTH_MINIMUM):
    """Qualify counties on cleaned calendar coverage, stable identity and continuity alone."""
    counties = defaultdict(list)
    for row in rows:
        counties[row['fips_code']].append(row)
    candidates = []
    expected_months = {(year, month) for year in YEARS for month in range(1, 13)}
    for fips, observed in sorted(counties.items()):
        geography = {(row['state'], row['county']) for row in observed}
        months = {(row['year'], row['month']): row['clean'] for row in observed}
        if len(geography) != 1 or set(months) != expected_months or len(observed) != len(months):
            continue
        state, county = next(iter(geography))
        if fips[:2] != STATE_ORDER.get(state):
            continue
        capacity = {(y, m): monthrange(y, m)[1] * 96 for y, m in months}
        annual = {y: (sum(months[y, m] for m in range(1, 13)) /
                      sum(capacity[y, m] for m in range(1, 13))) for y in YEARS}
        minimum_month = min(months[key] / capacity[key] for key in months)
        if min(annual.values()) >= annual_minimum and minimum_month >= month_minimum:
            candidates.append({'fips_code': fips, 'county': county, 'state': state, 'annual_coverage': annual,
                               'min_annual_coverage': min(annual.values()), 'min_month_coverage': minimum_month,
                               'clean': sum(months.values())})
    return candidates


def select_counties(rows):
    """Freeze the best-covered four per state and seed-17 spatial roles before labeling."""
    state_names = list(STATE_ORDER)
    attempts = []
    for annual, month in COVERAGE_TIERS:
        qualified = qualify_counties(rows, annual, month)
        ranked = {state: sorted((item for item in qualified if item['state'] == state),
                                key=lambda item: (-item['min_annual_coverage'], item['fips_code']))
                  for state in STATE_ORDER}
        available = {state: len(counties) for state, counties in ranked.items()}
        attempts.append({'annual': annual, 'month': month, 'qualified_per_state': available})
        print(f'Coverage tier {annual:.0%} annual / {month:.0%} monthly: {available}', flush=True)
        if any(available[state] < 4 for state in ORIGINAL):
            continue
        if not set(ORIGINAL.values()) <= {item['fips_code'] for item in qualified}:
            continue
        reserves = iter(state for state in state_names[5:] if available[state] >= 4)
        states = [state if available[state] >= 4 else next(reserves, None) for state in state_names[:5]]
        if None not in states:
            break
    else:
        raise ValueError(f'Could not qualify balanced states under documented coverage tiers: {attempts}')

    selected = []
    for index, state in enumerate(states):
        original_fips = ORIGINAL.get(state)
        pool = ranked[state]
        if original_fips is not None:
            originals = [item for item in pool if item['fips_code'] == original_fips]
            if len(originals) != 1:
                raise ValueError(f'Original county did not meet coverage: {original_fips}')
            pool = originals + [item for item in pool if item['fips_code'] != original_fips]
        group = pool[:4]
        withheld = min((item['fips_code'] for item in group if item['fips_code'] != original_fips),
                       key=lambda code: hashlib.sha256(f'17:{code}'.encode()).hexdigest())
        for item in group:
            role = 'unseen_state' if index == 4 else 'unseen_county' if item['fips_code'] == withheld else 'seen'
            selected.append({**item, 'role': role, 'original': item['fips_code'] == original_fips})
    return selected, available, attempts


def monthly_coverage(raw, year):
    """Apply the production validity and duplicate/conflict semantics before counting slots."""
    valid = (raw.filter(F.substring('fips_code', 1, 2).isin(list(STATE_ORDER.values())))
             .withColumn('timestamp', F.expr("try_to_timestamp(run_start_time, 'yyyy-MM-dd HH:mm:ss')"))
             .filter(F.col('fips_code').rlike('^[0-9]{5}$')
                     & F.col('run_start_time').rlike(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
                     & (F.year('timestamp') == year) & (F.unix_timestamp('timestamp') % 900 == 0)
                     & F.col('customers_out').rlike('^[0-9]+$')
                     & F.expr('try_cast(customers_out as bigint)').isNotNull()
                     & F.col('county').isNotNull() & F.col('state').isNotNull()))
    source_identity = F.struct('county', 'state', 'customers_out', 'run_start_time')
    # Equality of the least and greatest source variants detects all conflicting keys.
    clean_keys = (valid.groupBy('fips_code', 'timestamp')
                  .agg(F.min(source_identity).alias('source'), F.max(source_identity).alias('last_source'))
                  .filter(F.col('source') == F.col('last_source'))
                  .select('fips_code', 'timestamp', 'source.state', 'source.county'))
    return (clean_keys.groupBy('fips_code', 'state', 'county', F.month('timestamp').alias('month'))
            .agg(F.count('*').alias('clean'), F.min('timestamp').cast('string').alias('first_utc'),
                 F.max('timestamp').cast('string').alias('last_utc'))
            .withColumn('year', F.lit(year)))


def development_inputs():
    """Pin the four already-inventoried development inputs by path and SHA-256."""
    inventory = read_json(ROOT / 'reports/source_manifest.json')['files']
    inputs = []
    for year in YEARS:
        path = f'data/raw/eaglei_outages_{year}.csv'
        record = next(item for item in inventory if item['path'] == path)
        source = ROOT / path
        if sha256(source) != record['sha256']:
            raise ValueError(f'Development source differs from inventory: {path}')
        inputs.append({'year': year, 'path': path, 'bytes': source.stat().st_size,
                       'sha256': record['sha256']})
    return inputs


def coverage_phase(spark, reports):
    manifest_path = reports / 'cohort.json'
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    inputs = development_inputs()
    monthly = []
    for item in inputs:
        year = item['year']
        checkpoint = reports / f'coverage_{year}.json'
        if checkpoint.exists():
            evidence = read_json(checkpoint)
            if evidence['input'] != item or evidence['state_order'] != STATE_ORDER:
                raise ValueError(f'Coverage checkpoint inputs changed: {checkpoint}')
        else:
            started = time.perf_counter()
            counts = monthly_coverage(read_source(spark, [ROOT / item['path']]), year)
            evidence = {'input': item, 'state_order': STATE_ORDER,
                        'rows': [row.asDict() for row in counts.collect()], 'seconds': time.perf_counter() - started}
            write_new(checkpoint, evidence)
        monthly.extend(evidence['rows'])
        print(f'{year}: {len(evidence["rows"]):,} coverage summaries in {evidence["seconds"]:.1f}s', flush=True)
    selection, available, attempts = select_counties(monthly)
    write_new(manifest_path, {'inputs': inputs, 'county_selection': selection, 'qualified_per_state': available,
                              'state_order': STATE_ORDER, 'min_annual_coverage': attempts[-1]['annual'],
                              'min_monthly_coverage': attempts[-1]['month'], 'coverage_attempts': attempts, 'spatial_seed': 17,
                              'label_fields_read_for_selection': False})
    print('Frozen county roles:', [(x['fips_code'], x['role']) for x in selection], flush=True)


def extract_year(spark, item, selected, destination):
    """Filter one raw year to frozen county IDs and persist a native Spark checkpoint."""
    raw = read_source(spark, [ROOT / item['path']]).filter(F.col('fips_code').isin(selected))
    bucket = F.concat(F.lit('s'), F.substring('fips_code', 1, 2))
    raw.withColumn('bucket', bucket).write.mode('errorifexists').partitionBy('bucket').parquet(str(destination))
    persisted = spark.read.parquet(str(destination))
    counts = {row.fips_code: row['count'] for row in persisted.groupBy('fips_code').count().collect()}
    if set(counts) != set(selected):
        raise ValueError(f'Selected counties are missing in {item["year"]}')
    return {'year': item['year'], 'county_counts': counts, 'raw': sum(counts.values())}


def prepare_state(spark, state, subset, artifacts):
    """Run the original cleaning and feature/label code across all four years in one state."""
    prefix = f's{STATE_ORDER[state]}'
    paths = [str(artifacts / 'bronze' / str(year) / f'bucket={prefix}') for year in YEARS]
    raw = spark.read.parquet(*paths).cache()
    try:
        silver, quarantine, counts = clean(raw)
        silver_path = artifacts / 'silver' / prefix
        silver.write.mode('errorifexists').parquet(str(silver_path))
        quarantine_path = artifacts / 'quarantine' / prefix
        quarantine.write.mode('errorifexists').parquet(str(quarantine_path))
    finally:
        spark.catalog.clearCache()

    stored_silver = spark.read.parquet(str(silver_path)).cache()
    try:
        labels = audit_labels(features(stored_silver))
        labels = labels.select('fips_code', 'state', 'county', 'timestamp', *PREDICTORS, 'candidate_y',
                               'split', 'future_slots', 'label_complete', 'future_max_gap_seconds')
        for col in ['lag_15m', 'lag_60m', 'delta_60m']:
            labels = labels.withColumn(f'{col}_missing', F.col(col).isNull().cast('double'))
        out = artifacts / 'labels' / prefix
        labels.write.mode('errorifexists').partitionBy('split').parquet(str(out))
    finally:
        spark.catalog.clearCache()

    persisted = spark.read.parquet(str(out))
    eligible = F.col('candidate_y').isNotNull() & F.col('split').isin('train', 'validation')
    summaries = (persisted.groupBy('fips_code', 'state', 'county', F.year('timestamp').alias('year'), 'split')
                 .agg(F.count('*').alias('clean'), F.sum(eligible.cast('int')).alias('eligible'),
                      F.sum(F.coalesce((eligible & (F.col('candidate_y') == 1)), F.lit(False)).cast('int')).alias('positive'),
                      F.sum(F.col('label_complete').cast('int')).alias('complete_future'),
                      F.sum((F.col('customers_out_t') > 0).cast('int')).alias('positive_current'))
                 .collect())
    summary_rows = [row.asDict() for row in summaries]
    actual = {code: sum(row['clean'] for row in summary_rows if row['fips_code'] == code)
              for code in {row['fips_code'] for row in summary_rows}}
    expected = {item['fips_code']: item['clean'] for item in subset}
    if actual != expected or sum(actual.values()) != counts['silver']:
        raise ValueError(f'Coverage and production cleaning disagree for {state}: {actual} vs {expected}')
    metadata = {(item['fips_code'], item['county'], item['state']) for item in subset}
    if not all((row['fips_code'], row['county'], row['state']) in metadata and row['year'] in YEARS
               and row['split'] in {'train', 'validation', 'purged'} for row in summary_rows):
        raise ValueError(f'Unapproved geography, year, or split in {state}')
    rejected = [row.asDict() for row in spark.read.parquet(str(quarantine_path)).groupBy('reason').count().collect()]
    if sum(row['count'] for row in rejected) != counts['invalid'] + counts['conflict_rows']:
        raise ValueError(f'Quarantine count mismatch for {state}')
    return {'state': state, 'prefix': prefix, 'counts': counts, 'by_county_year_split': summary_rows,
            'quarantine_reasons': rejected}


def prepare_phase(spark, reports, artifacts):
    """Materialize isolated native checkpoints, reconciling each state independently."""
    audit_path = reports / 'data_audit.json'
    if audit_path.exists():
        raise FileExistsError(audit_path)
    cohort = read_json(reports / 'cohort.json')
    if development_inputs() != cohort['inputs']:
        raise ValueError('Development inputs differ from the frozen cohort manifest')
    selected = [item['fips_code'] for item in cohort['county_selection']]
    start = time.perf_counter()
    disk_before = shutil.disk_usage(artifacts).free
    annual = []
    for item in cohort['inputs']:
        year = item['year']
        checkpoint = reports / f'bronze_{year}.json'
        if checkpoint.exists():
            evidence = read_json(checkpoint)
        else:
            then = time.perf_counter()
            evidence = extract_year(spark, item, selected, artifacts / 'bronze' / str(year))
            evidence['seconds'] = time.perf_counter() - then
            write_new(checkpoint, evidence)
        annual.append(evidence)
        print(f'{year}: {evidence["raw"]:,} selected raw rows in {evidence["seconds"]:.1f}s', flush=True)

    states = []
    for state in dict.fromkeys(item['state'] for item in cohort['county_selection']):
        subset = [item for item in cohort['county_selection'] if item['state'] == state]
        checkpoint = reports / f'state_{STATE_ORDER[state]}.json'
        if checkpoint.exists():
            evidence = read_json(checkpoint)
        else:
            then = time.perf_counter()
            print(f'Processing {state} with {psutil.virtual_memory().available / 2**30:.2f} GiB available', flush=True)
            evidence = prepare_state(spark, state, subset, artifacts)
            evidence['seconds'] = time.perf_counter() - then
            write_new(checkpoint, evidence)
        states.append(evidence)
        print(f'{state}: {evidence["counts"]}, {evidence["seconds"]:.1f}s', flush=True)
    if sum(item['raw'] for item in annual) != sum(item['counts']['raw'] for item in states):
        raise ValueError('Bronze and state cleaning counts disagree')
    write_new(audit_path, {'status': 'VERIFIED', 'inputs': cohort['inputs'], 'scope': '2018–2021 selected counties',
                          'writer': 'Native Spark Parquet', 'raw_by_year': annual, 'state_audits': states,
                          'counts': {key: sum(item['counts'][key] for item in states) for key in states[0]['counts']},
                          'seconds': time.perf_counter() - start, 'free_bytes_before': disk_before,
                          'free_bytes_after': shutil.disk_usage(artifacts).free,
                          'spark_version': spark.version, 'shuffle_partitions': 16})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['coverage', 'prepare'])
    parser.add_argument('run_id')
    args = parser.parse_args()
    reports, artifacts = directories(args.run_id)
    reports.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    scratch = artifacts / 'spark_scratch'
    scratch.mkdir(exist_ok=True)
    os.environ['SPARK_LOCAL_DIRS'] = str(scratch)
    spark = make_spark(f'GridRescue expansion {args.phase}')
    try:
        spark.conf.set('spark.sql.shuffle.partitions', '16')
        hadoop = spark._jvm.org.apache.hadoop
        if os.name == 'nt' and not hadoop.io.nativeio.NativeIO.isAvailable():
            raise RuntimeError('Use the verified native Windows Spark configuration')
        print(f'Spark {spark.version}, Hadoop {hadoop.util.VersionInfo.getVersion()}, '
              f'available RAM {psutil.virtual_memory().available / 2**30:.2f} GiB', flush=True)
        if args.phase == 'coverage':
            coverage_phase(spark, reports)
        else:
            prepare_phase(spark, reports, artifacts)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()

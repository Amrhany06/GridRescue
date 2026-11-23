"""Build the cloud dataset with the original UTC Spark transformations."""
from collections import defaultdict, deque
from datetime import date
import hashlib
import os
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from pyspark.sql import SparkSession, functions as F

from cloud_core import (YEARS, checkpoint, load, require_resources, save, select_tiers,
                        stage_file, validate_training_counties)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for directory in (ROOT / 'src', HERE.parent / 'local_improvement'):
    sys.path.insert(0, str(directory))
from gridrescue.pipeline import SOURCE, audit_labels, clean, features, read_source
from gridrescue.modeling import FEATURE_COLUMNS
from history import ADDED, history_features, validate_silver

KEY = ['fips_code', 'timestamp', 'candidate_y']
NUMERIC = FEATURE_COLUMNS + ADDED
COLUMNS = [*KEY, 'state', 'future_slots', *NUMERIC]
REGIONS = {
    'Northeast': '09 23 25 33 44 50 34 36 42',
    'Midwest': '17 18 26 39 55 19 20 27 29 31 38 46',
    'South': '10 11 12 13 24 37 45 51 54 01 21 28 47 05 22 40 48',
    'West': '04 08 16 30 32 35 49 56 02 06 15 41 53',
}


def spark_session(scratch, memory='4g', threads=4):
    """Keep Spark scratch on the VM and use the archived UTC parser settings."""
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ['SPARK_LOCAL_DIRS'] = str(scratch)
    os.environ.setdefault('PYSPARK_PYTHON', sys.executable)
    os.environ.setdefault('PYSPARK_DRIVER_PYTHON', sys.executable)
    os.environ.setdefault('SPARK_LOCAL_IP', '127.0.0.1')
    spark = (SparkSession.builder.master(f'local[{threads}]').appName('GridRescue cloud expansion')
             .config('spark.driver.memory', memory).config('spark.sql.session.timeZone', 'UTC')
             .config('spark.sql.legacy.timeParserPolicy', 'CORRECTED').config('spark.sql.shuffle.partitions', '48')
             .config('spark.sql.adaptive.enabled', 'true').config('spark.ui.enabled', 'false').getOrCreate())
    spark.sparkContext.setLogLevel('WARN')
    return spark


def fingerprint(frame):
    """Hash exact row keys and labels using a sorted, portable binary representation."""
    data = frame[KEY].copy()
    data['fips_code'] = data.fips_code.astype(str)
    full_time = pd.to_datetime(data.timestamp, utc=True)
    data['timestamp'] = full_time.astype('datetime64[s, UTC]')
    if (data.empty or data.isna().any().any() or not data.fips_code.str.fullmatch('[0-9]{5}').all()
            or not data.candidate_y.isin([0, 1]).all() or data.duplicated(KEY[:2]).any()):
        raise ValueError('Missing, malformed, or duplicate row identities/labels')
    seconds = data.timestamp.astype('int64')
    if (not full_time.eq(data.timestamp).all() or not (seconds % 900 == 0).all()
            or not data.timestamp.dt.year.between(YEARS[0], YEARS[-1]).all()):
        raise ValueError('Rows fall outside the quarter-hour development calendar')
    data = data.sort_values(['timestamp', 'fips_code'], kind='stable')
    packed = np.empty(len(data), dtype=[('fips', 'S5'), ('epoch', '<i8'), ('label', 'u1')])
    packed['fips'] = data.fips_code.to_numpy()
    packed['epoch'] = data.timestamp.astype('int64').to_numpy()
    packed['label'] = data.candidate_y.to_numpy()
    return dict(rows=len(data), positive=int(packed['label'].sum()), sha256=hashlib.sha256(packed).hexdigest())


def exact_period(frame, lo, end):
    timestamp = pd.to_datetime(frame.timestamp, utc=True)
    if not (timestamp.ge(pd.Timestamp(lo, tz='UTC')) &
            timestamp.lt(pd.Timestamp(end, tz='UTC') - pd.DateOffset(hours=3))).all():
        raise ValueError(f'Rows outside the purged period [{lo}, {end})')


def read_rows(paths, counties=None, columns=COLUMNS, start=None, end=None, timestamps=None):
    """Pull only selected eligible Parquet rows, with Arrow filters applied first."""
    if not paths:
        raise ValueError('No Parquet checkpoint paths')
    files = [str(part) for path in paths for part in sorted(path.glob('part-*.parquet'))]
    dataset = ds.dataset(files, format='parquet')
    predicate = ds.field('fips_code').isin(counties) if counties is not None else None
    time_type = dataset.schema.field('timestamp').type
    for bound, op in ((start, 'start'), (end, 'end')):
        if bound is not None:
            value = pd.Timestamp(bound).to_pydatetime()
            value = value.replace(tzinfo=None) if time_type.tz is None else value
            term = ds.field('timestamp') >= value if op == 'start' else ds.field('timestamp') < value
            predicate = term if predicate is None else predicate & term
    if timestamps is not None:
        utc = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True))
        terms = utc.tz_localize(None) if time_type.tz is None else utc
        condition = ds.field('timestamp').isin(pa.array(terms, type=time_type))
        predicate = condition if predicate is None else predicate & condition
    # Arrow transfers compact integer/flag columns until each fit casts its numerics.
    table = dataset.to_table(columns=columns, filter=predicate, use_threads=False)
    frame = table.to_pandas(split_blocks=True)
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True).astype('datetime64[ns, UTC]')
    frame['fips_code'] = pd.Categorical(frame.fips_code, categories=sorted(frame.fips_code.unique()))
    if 'state' in frame:
        frame['state'] = frame.state.astype('category')
    frame.sort_values(['timestamp', 'fips_code'], inplace=True, ignore_index=True)
    return frame


def cohort_roles(reference):
    roles = {row['fips_code']: row['role'] for row in reference['counties']}
    seen = sorted(code for code, role in roles.items() if role == 'seen')
    withheld = sorted(set(roles) - set(seen))
    if len(roles) != 20 or len(seen) != 12 or len(withheld) != 8:
        raise ValueError('Frozen evaluation county manifest must contain 12 seen and 8 withheld counties')
    if {code for code, role in roles.items() if role == 'unseen_state'} != {code for code in roles if code.startswith('36')}:
        raise ValueError('The entirely unseen state must remain New York')
    validate_training_counties(seen, withheld)
    return roles, seen, withheld


def eligible_features(raw, all_codes, train_codes, eval_codes):
    """Use the same cleaning, exact lags, missing flags and future labels as Windows."""
    silver, _, reconciled = clean(raw)
    validate_silver(silver, all_codes)
    observed = {row.fips_code: (row['count'], row.identities) for row in silver.groupBy('fips_code').agg(
        F.count('*').alias('count'), F.countDistinct(F.struct('state', 'county')).alias('identities')).collect()}
    if set(observed) != set(all_codes) or any(item[1] != 1 for item in observed.values()):
        raise ValueError(f'Missing counties or inconsistent geography in Silver: {observed}')
    base = audit_labels(features(silver))
    for feature in ('lag_15m', 'lag_60m', 'delta_60m'):
        base = base.withColumn(f'{feature}_missing', F.col(feature).isNull().cast('double'))
    eligible = base.where(F.col('candidate_y').isin(0, 1) &
                          (((F.col('split') == 'train') & F.col('fips_code').isin(train_codes)) |
                           ((F.col('split') == 'validation') & F.col('fips_code').isin(eval_codes))))
    return (eligible.join(history_features(silver), KEY[:2], 'left').select('split', *COLUMNS),
            reconciled, {code: count for code, (count, _) in observed.items()})


def verify_fixture(spark, package=HERE):
    """Rebuild a small trusted sample from exact archived Bronze source tokens."""
    fixture = load(package / 'fixture_expected.json')
    roles, seen, _ = cohort_roles(load(package / 'reference_manifest.json'))
    raw = read_source(spark, [package / 'fixture_bronze.csv'])
    try:
        result, _, _ = eligible_features(raw, sorted(roles), seen, sorted(roles))
        expected = pd.DataFrame(fixture['rows'])
        expected['timestamp'] = pd.to_datetime(expected.timestamp, utc=True)
        keys = [(r.fips_code, int(r.timestamp.timestamp())) for r in expected.itertuples()]
        matching = spark.createDataFrame(keys, 'fips_code string, epoch long')
        found = result.withColumn('epoch', F.unix_timestamp('timestamp')).join(matching, ['fips_code', 'epoch'])
        actual = found.drop('timestamp').toPandas()
        # Explicitly use epoch seconds to avoid Spark's Python-side local-time conversion.
        actual['timestamp'] = pd.to_datetime(actual.pop('epoch'), unit='s', utc=True)
        verify_features(actual, expected)
        return {'rows': len(actual), 'counties': actual.fips_code.nunique(), 'key_label_digest': fingerprint(actual)}
    finally:
        spark.catalog.clearCache()


def verify_features(actual, expected):
    order = ['fips_code', 'timestamp']
    actual, expected = (frame.assign(fips_code=frame.fips_code.astype(str), state=frame.state.astype(str),
                                      timestamp=pd.to_datetime(frame.timestamp, utc=True).astype('datetime64[ns, UTC]'))
                        .sort_values(order).reset_index(drop=True) for frame in (actual, expected))
    columns = [*KEY, 'state', 'split', 'future_slots']
    pd.testing.assert_frame_equal(actual[columns], expected[columns], check_dtype=False)
    np.testing.assert_allclose(actual[NUMERIC].to_numpy(dtype=float), expected[NUMERIC].to_numpy(dtype=float),
                               rtol=1e-12, atol=1e-8, equal_nan=True)


def training_parity_sample(frame):
    """Select the earliest archived row per county and per within-state stratum."""
    ordered = frame.sort_values(['timestamp', 'fips_code'], kind='stable')
    strata = ordered.assign(gap=ordered.reporting_coverage_180m.lt(1),
                            severity=pd.cut(ordered.customers_out_t, [0, 50, 200, 400, 1000, np.inf]))
    indices = strata.drop_duplicates('fips_code').index
    for column in ('hour_utc', 'gap', 'severity'):
        indices = indices.union(strata.drop_duplicates(['state', column]).index, sort=False)
    return ordered.loc[ordered.index.isin(indices), COLUMNS]


def verify_tier_a_features(actual, expected, split):
    expected = expected.assign(timestamp=pd.to_datetime(expected.timestamp, utc=True).astype('datetime64[ns, UTC]'))
    fingerprint(expected)
    matched = actual.merge(expected[KEY[:2]], on=KEY[:2], validate='one_to_one')
    verify_features(matched.assign(split=split), expected.assign(split=split))


def monthly_coverage(raw, year):
    """Compute label-free report coverage with the pilot's conflict semantics."""
    state_codes = [code for values in REGIONS.values() for code in values.split() if code != '36']
    valid = (raw.filter(F.substring('fips_code', 1, 2).isin(state_codes))
             .withColumn('timestamp', F.expr("try_to_timestamp(run_start_time, 'yyyy-MM-dd HH:mm:ss')"))
             .filter(F.col('fips_code').rlike('^[0-9]{5}$')
                     & F.col('run_start_time').rlike(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
                     & (F.year('timestamp') == year) & (F.unix_timestamp('timestamp') % 900 == 0)
                     & F.col('customers_out').rlike('^[0-9]+$')
                     & F.expr('try_cast(customers_out as bigint)').isNotNull()
                     & F.col('county').isNotNull() & F.col('state').isNotNull()))
    identity = F.struct('county', 'state', 'customers_out', 'run_start_time')
    unique = (valid.groupBy('fips_code', 'timestamp')
              .agg(F.min(identity).alias('first'), F.max(identity).alias('last'))
              .where(F.col('first') == F.col('last')))
    return (unique.select('fips_code', F.col('first.county').alias('county'), F.col('first.state').alias('state'),
                          F.month('timestamp').alias('month')).groupBy('fips_code', 'county', 'state', 'month')
            .agg(F.count('*').alias('clean')).withColumn('year', F.lit(year)))


def rank_counties(rows, excluded, max_counties):
    """Freeze a deterministic region/state rotation using training coverage alone."""
    valid_states = {fips: region for region, values in REGIONS.items() for fips in values.split()}
    months = {(y, m): (date(y + (m == 12), m % 12 + 1, 1) - date(y, m, 1)).days * 96
              for y in YEARS[:3] for m in range(1, 13)}
    by_county = defaultdict(list)
    for row in rows:
        code = row['fips_code']
        if code not in excluded and code[:2] in valid_states and not code.startswith('36') and re.fullmatch('[0-9]{5}', code):
            by_county[code].append(row)
    by_state = defaultdict(list)
    for code, items in by_county.items():
        places = {(row['state'], row['county']) for row in items}
        counts = {(row['year'], row['month']): row['clean'] for row in items}
        if len(places) != 1 or set(counts) != set(months) or len(items) != len(counts):
            continue
        min_month = min(counts[key] / months[key] for key in months)
        annual = {y: sum(counts[key] for key in months if key[0] == y) / sum(
            months[key] for key in months if key[0] == y) for y in YEARS[:3]}
        if any(count < 0 or count > months[key] for key, count in counts.items()):
            raise ValueError(f'Invalid calendar coverage for {code}')
        if min(annual.values()) >= .65 and min_month >= .40:
            state, county = next(iter(places))
            by_state[code[:2]].append(dict(fips_code=code, state=state, county=county, region=valid_states[code[:2]],
                                          min_annual=min(annual.values()), min_month=min_month, clean=sum(counts.values())))
    pending = {state: deque(sorted(counties, key=lambda row: (-row['min_annual'], -row['min_month'], row['fips_code'])))
               for state, counties in by_state.items()}
    zones = {name: deque(code for code in sorted(states.split()) if code in pending) for name, states in REGIONS.items()}
    result = []
    while any(zones.values()) and len(result) < max_counties:
        for zone in zones.values():
            if zone and len(result) < max_counties:
                state = zone.popleft()
                result.append(pending[state].popleft())
                if pending[state]:
                    zone.append(state)
    return result


class Datasets:
    """Stage inputs on demand and publish verified partition checkpoints to Drive."""
    def __init__(self, vm, drive, raw_drive, pin, reference):
        self.vm, self.drive, self.raw_drive = vm, drive, raw_drive
        self.pin, self.reference = pin, reference
        self.roles, self.seen, self.withheld = cohort_roles(reference)

    def stage(self, name, build=None):
        def missing(_):
            raise RuntimeError(f'Required stage {name} is missing. Run its notebook cell first.')
        return checkpoint(self.vm, self.drive, name, missing if build is None else build)

    def source(self, year):
        if year not in YEARS:
            raise ValueError('Unapproved source year')
        pin = self.pin[year]
        return stage_file(self.raw_drive / pin['name'], self.vm.parent / 'raw' / pin['name'], pin)

    def bronze(self, spark, year, counties, scope):
        def build(out):
            raw = read_source(spark, [self.source(year)]).where(F.col('fips_code').isin(counties))
            (raw.withColumn('county_state', F.substring('fips_code', 1, 2))
             .repartition('county_state').write.partitionBy('county_state').parquet(str(out / 'data')))
        return self.stage(f'{scope}-bronze-{year}', build) / 'data'

    def features(self, spark, bronze, counties, train, development, name, clean_counts=None):
        def build(out):
            prefix = counties[0][:2]
            subsets = [str(path / f'county_state={prefix}') for path in bronze]
            raw = spark.read.parquet(*subsets).where(F.col('fips_code').isin(counties))
            try:
                frame, stats, observed = eligible_features(raw, counties, train, development)
                if clean_counts is not None and observed != clean_counts:
                    raise ValueError(f'Coverage and Silver disagree for {name}')
                frame = frame.cache()
                counts = [row.asDict() for row in frame.groupBy('split', 'fips_code', 'state').count().collect()]
                frame.repartition(4).write.partitionBy('split').parquet(str(out / 'rows'))
                save(out / 'counts.json', dict(counties=counties, rows=counts, clean=observed, reconciliation=stats))
            finally:
                spark.catalog.clearCache()
        return self.stage(name, build)

    def baseline(self, spark):
        all_codes = sorted(self.roles)
        bronze = [self.bronze(spark, year, all_codes, 'pilot') for year in YEARS]
        names = []
        for state in sorted({code[:2] for code in all_codes}):
            codes = [code for code in all_codes if code.startswith(state)]
            name = f'pilot-features-{state}'
            self.features(spark, bronze, codes, sorted(set(codes) & set(self.seen)), codes, name)
            names.append(name)

        def lock(out):
            fixture = pd.DataFrame(load(HERE / 'fixture_expected.json')['rows'])
            fixture['timestamp'] = pd.to_datetime(fixture.timestamp, utc=True).astype('datetime64[ns, UTC]')
            parity = load(HERE / 'tier_a_parity_reference.json')
            checked = {}
            for split, lo, end, expected_codes in (('train', '2018-01-01', '2021-01-01', self.seen),
                                                   ('validation', '2021-01-01', '2022-01-01', all_codes)):
                paths = self.paths(names, split)
                observed = read_rows(paths, columns=KEY)
                exact_period(observed, lo, end)
                if set(observed.fips_code) != set(expected_codes):
                    raise ValueError(f'Unexpected geography in pilot {split}')
                overall = fingerprint(observed)
                by_county = {code: fingerprint(rows) for code, rows in observed.groupby('fips_code', observed=True)}
                if {'overall': overall, 'by_county': by_county} != self.reference[split]:
                    raise ValueError(f'Cloud pilot {split} identities or labels differ from trusted Windows results. Stop.')
                sample = fixture.loc[fixture.split.eq(split)]
                sampled = read_rows(paths, sorted(sample.fips_code.unique()), timestamps=sample.timestamp.unique())
                matched = sampled.merge(sample[KEY[:2]], on=KEY[:2], how='inner', validate='one_to_one')
                verify_features(matched.assign(split=split), sample)
                sample = pd.DataFrame(parity['features'][split])
                sampled = read_rows(paths, sorted(sample.fips_code.unique()), timestamps=sample.timestamp.unique())
                verify_tier_a_features(sampled, sample, split)
                checked[split] = len(sample)
                print(f'Pilot {split} fingerprint matched: {overall}', flush=True)
            save(out / 'dataset.json', dict(pilot=names, reference=self.reference['validation']['overall'],
                                            parity_feature_rows=checked))
        return self.stage('pilot-verified', lock)

    def paths(self, names, split):
        if split not in ('train', 'validation'):
            raise ValueError('Only development feature splits are allowed')
        return [path for name in names if (path := self.stage(name) / 'rows' / f'split={split}').is_dir()]

    def expanded(self, spark, max_candidates):
        pilot = load(self.stage('pilot-verified') / 'dataset.json')
        yearly_coverage = []
        for year in YEARS[:3]:
            def coverage(out, year=year):
                require_resources(self.vm, 7, 12, f'Coverage scan {year}')
                result = monthly_coverage(read_source(spark, [self.source(year)]), year)
                result.write.parquet(str(out / 'coverage'))
            yearly_coverage.append(self.stage(f'coverage-{year}', coverage) / 'coverage')

        def shortlist(out):
            rows = (r.asDict() for r in spark.read.parquet(*map(str, yearly_coverage)).toLocalIterator())
            ranked = rank_counties(rows, self.roles, max_candidates)
            if not ranked:
                raise ValueError('No additional counties passed the predefined coverage filters')
            validate_training_counties([r['fips_code'] for r in ranked], self.withheld)
            save(out / 'shortlist.json', ranked)
        frozen_rank = load(self.stage('training-shortlist', shortlist) / 'shortlist.json')
        candidates = [row['fips_code'] for row in frozen_rank]
        clean_by_code = {row['fips_code']: row['clean'] for row in frozen_rank}
        bronze = [self.bronze(spark, year, candidates, 'expansion') for year in YEARS[:3]]
        names = []
        for state in sorted({code[:2] for code in candidates}):
            county_state = sorted(code for code in candidates if code.startswith(state))
            for start in range(0, len(county_state), 12):
                codes = county_state[start:start + 12]
                name = f'expansion-features-{state}-{start // 12}'
                self.features(spark, bronze, codes, codes, [], name, {code: clean_by_code[code] for code in codes})
                names.append(name)

        def tiers(out):
            counts = {}
            stage_by_county = {}
            for name in names:
                evidence = load(self.stage(name) / 'counts.json')
                stage_by_county.update({code: name for code in evidence['counties']})
                for row in evidence['rows']:
                    if row['split'] != 'train' or row['fips_code'] in counts:
                        raise ValueError(f'Unexpected or duplicate expanded county: {row}')
                    counts[row['fips_code']] = row['count']
            base = {code: self.reference['train']['by_county'][code]['rows'] for code in self.seen}
            tiers = select_tiers(base, [(code, counts.get(code, 0)) for code in candidates], self.withheld)
            states = {row['fips_code']: row['state'] for row in [*self.reference['counties'], *frozen_rank]}
            for tier in tiers.values():
                tier['states'] = sorted({states[code] for code in tier['counties']})
            save(out / 'dataset.json', dict(verified_pilot=pilot, tiers=tiers, feature_stages=names,
                                            feature_stage_by_county=stage_by_county,
                                            candidate_eligible_counts={code: counts.get(code, 0) for code in candidates},
                                            selection_used_target_values=False))
        return self.stage('expansion-verified', tiers)

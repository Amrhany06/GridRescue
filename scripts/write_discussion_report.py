"""Render discussion evidence directly from measured audits; never invent outputs."""
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def read(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8'))


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(str, headers)) + ' |',
                      '|' + '|'.join(['---'] * len(headers)) + '|',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


def save(name, text):
    path = REPORTS / name
    if path.exists() and path.read_text(encoding='utf-8') != text:
        backup = ROOT / 'artifacts/report_history' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') / name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    path.write_text(text, encoding='utf-8')


def label_totals(audit):
    by_split = defaultdict(lambda: defaultdict(int))
    for row in audit['label_summary']:
        key = 'unknown' if row['candidate_y'] is None else str(row['candidate_y'])
        by_split[row['split']][key] += row['count']
    return by_split


def main():
    sample, county = read('memory/sample/audit.json'), read('memory/county/audit.json')
    full, inventory = read('full_development_audit.json'), read('parsed_inventory.json')
    for audit in [sample, county]:
        assert audit['execution'].startswith('VERIFIED IN-MEMORY AUDIT ONLY')
        c = audit['counts']
        assert c['raw'] == c['invalid'] + c['exact_duplicates_removed'] + c['conflict_rows'] + c['silver']
    assert full['status'] == 'VERIFIED_FULL_DEVELOPMENT_INTEGRITY_ONLY'
    nb = read('notebook_execution.json')
    tests = (REPORTS / 'verification/tests.txt').read_text(encoding='utf-8')
    result = re.search(r'Ran (\d+) tests', tests)
    errors=re.findall(r'^ERROR: (test_\w+)',tests,re.MULTILINE)
    failed_match=re.search(r'FAILED \(([^)]+)\)',tests)
    issue_count=sum(map(int,re.findall(r'=(\d+)',failed_match[1]))) if failed_match else 0
    test_summary=f"{result[1]} tests executed: {int(result[1])-issue_count} passed" + (f"; {failed_match[0]}" if failed_match else '; all passed')
    now = datetime.now(timezone.utc).isoformat()
    source_table = table(['Year', 'Parsed records', 'Invalid rows (any reason)', 'Null count tokens', 'Off-grid timestamps', 'Valid before deduplication'],
                         [[f['year'], f"{f['parsed_rows']:,}", f"{f['invalid_rows_any_reason']:,}", f"{f['null_customers_out']:,}", f"{f['off_grid_timestamp']:,}", f"{f['valid_rows_before_deduplication']:,}"] for f in full['files']])
    counts_table = table(['Stage', 'Prefix smoke subset', 'Three counties, full development dates'],
                         [[key, f"{sample['counts'][key]:,}", f"{county['counts'][key]:,}"] for key in ['raw', 'invalid', 'exact_duplicates_removed', 'conflict_rows', 'silver']])
    invalid_table=table(['Scope','Quarantine reason combination','Rows'],[[title,r['reason'],f"{r['count']:,}"] for title,audit in [('Prefix',sample),('Counties',county)] for r in audit['invalid_reasons']])
    splits = []
    for title, audit in [('Prefix', sample), ('Counties', county)]:
        for split, values in sorted(label_totals(audit).items()):
            eligible = values['0'] + values['1']
            splits.append([title, split, f"{eligible:,}", f"{values['1']:,}", f"{values['0']:,}", f"{values['unknown']:,}", f"{values['1']/eligible:.2%}" if eligible else 'n/a'])
    split_table = table(['Scope', 'Split', 'Eligible', 'Positive', 'Negative', 'Unlabelled', 'Positive share among eligible'], splits)
    county_table = table(['County / FIPS', 'Year', 'Observed days', 'Clean anchors', 'Eligible', 'Positive', 'Negative'],
                         [[f"{r['county']} / {r['fips_code']}", r['year'], r['observed_days'], f"{r['observed_anchors']:,}", f"{r['eligible']:,}", f"{r['positive'] or 0:,}", f"{r['negative'] or 0:,}"] for r in county['coverage_by_county_year']])
    outliers = table(['Scope', 'Median', 'Q3', 'IQR upper fence', 'Above fence', 'Maximum retained'],
                     [[title, audit['outliers']['approx_quantiles_25_50_75_99'][1], audit['outliers']['approx_quantiles_25_50_75_99'][2], audit['outliers']['iqr_upper_fence'], f"{audit['outliers']['above_fence']:,}", f"{audit['outliers']['max']:,}"] for title, audit in [('Prefix', sample), ('Counties', county)]])
    feature=read('feature_feasibility.json')
    feature_table=table(['Scope','Year','Observed months','Hours','Weekdays','Missing exact 15m lag','Missing exact 60m lag'],
                        [[scope,r['year'],r['observed_months'],r['observed_hours'],r['observed_weekdays'],f"{r['missing_exact_15m_lag']:,}",f"{r['missing_exact_60m_lag']:,}"]
                         for scope in ['sample','county'] for r in feature[scope]['by_year']])
    prep=read('preparation_validation.json') if (REPORTS/'preparation_validation.json').exists() else None
    prep_text=(f"The fitted in-memory preparation transformed **{prep['transformed_rows']:,} rows into {prep['vector_dimension']}-element vectors**, with {prep['nonfinite_vectors']} non-finite vectors and {prep['wrong_dimension_vectors']} dimension errors. Actual training medians, scaler means/std and constant predictors are saved as JSON statistics in `preparation_memory.json`; validation counts are in `preparation_validation.json`. These JSON files are evidence, not a persisted Spark pipeline." if prep else 'See the executed Task 2 notebook for fitted preparation checks; no Spark pipeline artifact is claimed saved.')
    nb_table = table(['Notebook', 'Status', 'Executed code cells'], [[r['name'], r['status'], r.get('executed_code_cells', 'incomplete')] for r in nb['notebooks']])
    exclusions = []
    for title, audit in [('Prefix', sample), ('Counties', county)]:
        unknown = sum(r['count'] for r in audit['label_summary'] if r['candidate_y'] is None)
        zero_complete = sum(r['count'] for r in audit['label_summary'] if r['candidate_y'] is None and r['future_slots'] == 12)
        purged = sum(r['all_anchors'] for r in audit['splits'] if r['split'] == 'purged')
        exclusions.append([title, f'{unknown:,}', f'{zero_complete:,}', f'{purged:,}'])
    exclusion_table = table(['Scope', 'Unlabelled anchors', 'Complete windows with nonpositive anchor', 'Boundary-purged anchors'], exclusions)
    text = f'''# Task 1–2 discussion evidence

Generated {now}. No Task 3 model was trained. Candidate labels remain **unapproved**. Analytical success and storage success are separate.

## What ran on which data

- **Complete development CSVs (2018–2021):** Spark FAILFAST parsing and aggregate integrity checks over **{full['parsed_development_rows_so_far']:,} records**. No full-population deduplication, feature/label materialization or EDA is claimed.
- **Prefix debugging subset:** first 100,000 records per development year, 400,000 total; in-memory cleaning, duplicate/conflict reconciliation, gaps, outliers, past-only features and provisional label audit. Prefixes are not a random population sample.
- **Selected counties:** fixed FIPS 06037 (Los Angeles), 12086 (Miami-Dade), 48201 (Harris), selected before label inspection; all source dates in 2018–2021, 418,374 records. Same in-memory transformations and feasibility audit. These well-covered counties are geographic examples, not an approved modeling cohort.
- **2022:** integrity-only CSV record/shape count and prior byte/hash inventory. No quality distribution, predictors, labels, imputation, model development, tuning or scoring used 2022.

## Source counts and quality

{source_table}

2022 has **25,796,465 parsed CSV data records**, verified with Python's CSV parser only. All five files contain **{inventory['csv_parsed_record_total']:,} data records**. Adding five headers gives **{inventory['records_including_headers']:,}**, exactly the supplied inventory total. Every supplied annual total is also one higher than its parsed data count. This explains the arithmetic discrepancy; the upstream author's counting method was not independently verified.

The full development audit found no null FIPS/county/state/time tokens, malformed timestamps, invalid FIPS, or parsed timestamps outside the source year. Invalid-count totals equal missing-count totals in each year. Reason flags overlap, so null counts plus off-grid counts must not be summed as disjoint removals. Every annual source ends at **December 31 00:00 UTC**; the last calendar day is not fully covered. Source strings lack UTC offsets; UTC interpretation follows the supplied documentation.

## What happened to each row

Original CSV bytes are unchanged after relocation into `data/raw/`; hashes match the previous manifest. CSV tokens are read as strings so FIPS leading zeros survive. Counts must be nonnegative integer tokens fitting a signed 64-bit integer; identity/geography/time must be present, timestamps parse strictly, and observation times must lie on the quarter-hour grid. Invalid rows are quarantined, never imputed. Exact valid duplicate rows are removed once. All distinct variants of a conflicting county-time key are quarantined. The checked identity is raw = invalid + exact duplicate removals + conflict variants + Silver.

These are in-memory quarantine/Silver DataFrames; persistent Bronze, quarantine, Silver and Gold files have not been verified or claimed saved.

{counts_table}

{invalid_table}

Both real scopes had zero exact duplicates and zero conflicting-key variants. This does not establish full-population duplicate rates. Both in-memory runs assert Gold row count equals Silver. Missing county-time rows remain absent; no zeros, interpolation or new observations are inserted. County-year gap counts describe only observed endpoints, excluding unknown leading/trailing coverage. The selected counties have {sum(r['internal_missing_slots'] for r in county['gaps']):,} missing internal quarter-hour slots across their county-years.

## Outliers and feature definitions

{outliers}

Quantiles use Spark approximate quantiles with relative rank tolerance 0.001. The IQR fence flags rarity, not invalidity; all valid extreme counts are retained. Capping/deletion could erase severe events. log1p is a display transform only.

X has **13 numeric predictors**: current count; exact same-county 15m/60m lags; current-minus-60m change; observed past-only [t−60m,t] mean/population variance; historical slot count (1–5); UTC hour/weekday/month; three missingness indicators. See [exact definitions](FEATURE_DEFINITIONS.md). IDs and geography remain audit/grouping metadata, so no categorical encoder is fitted. Missing lag/change predictors may receive training medians; missing observations and y never do. StandardScaler learns training mean/sample standard deviation only. Task 2's notebook reports the actual fitted values and transformed checks separately from saved artifacts.

{feature_table}

Prefix training contains only January: month has zero training standard deviation and is scaled to zero. It does not validate seasonal effects. The selected-county audit actually observed all 12 months, 24 hours and seven weekdays in each year. Exact lags remain missing where the requested timestamp is absent; those missing counts are measured above, not inferred from row offsets. The historical slot count stayed within 1–5 in both scopes. {prep_text}

## Provisional y, exclusions and splits

y=1 when a future reported count in (t,t+3h] reaches current + max(200, 50% of current). Current count must be positive. **Both classes require all 12 exact future quarter-hour slots**. Missing future observations remain unknown, even if a partial future trace contains a threshold crossing. Candidate labels are audit outcomes, not scientific approval.

{split_table}

{exclusion_table}

Training is 2018–2020; validation is 2021. The final 2022 test is sealed and **no test predictor/label rows are materialized**. An absent test row count here means unprocessed, not an empty final-test dataset. Horizon-crossing anchors would be purged; both real scopes have zero such anchors because source years end before the final three hours. Boundary behavior is exercised by the synthetic regression fixture, not a fabricated real example.

## Temporal feasibility and selection

{county_table}

Each selected county has observations on every calendar date in each source year, including 366 dates in 2020; date presence does not imply every quarter-hour is present, and December 31 contains only the source endpoint. Both classes occur in every selected county-year. Eligible prevalence differs greatly from the January prefix subset. Coverage-based complete-case selection and the fixed populous counties can favor sustained, well-reported outages; neither cohort's prevalence generalizes to all counties. Future reporting completeness is unknown at inference time, so retrospective complete-case eligibility is not an operationally available prediction-time selector. Overlapping three-hour anchors are correlated and are not independent outage events.

Actual positive, negative and incomplete traces are in `reports/memory/{{sample,county}}/label_traces.json`. No real boundary example exists in either scope. Included-versus-all severity and county/state eligibility appear in each audit's `selection_bias` and `coverage_by_county_year` fields. These diagnostics do not justify changing the target or restricting the eventual modeling population without approval.

An independent standard-library check verified 18 exported traces against the exact expected timestamp set, source counts, threshold, maximum and candidate class; see `real_trace_checks.json`. Example: FIPS 01073 at 2018-01-01 00:00 UTC has current count 6, threshold 206, all 12 future slots, future maximum 242, and candidate y=1. Miami-Dade at the same anchor has current 658, threshold 987, future maximum 2,043 and all 12 slots, also candidate y=1.

## Leakage prevention and verification

Exact timestamp joins avoid mistaking four previous observations for one hour. Features use no future observations; mutation fixtures verify later measurements and other counties cannot alter an anchor's predictors. Future maxima, completeness, threshold and y are excluded from X. Chronological splitting and horizon purging prevent cross-partition outcome leakage. Preparation fits only eligible training rows and must be refitted inside each future CV fold. No target-based feature selection or 2022 tuning took place.

{nb_table}

Notebook execution starts a fresh kernel for each notebook and saves outputs. See `notebook_execution.json` for the actual latest status. **Tests:** {test_summary}; remaining error(s): {', '.join(errors) or 'none'}. Details and exit codes are in `verification/tests.txt` and `verification/tests.json`. Dependency, syntax and layout checks have separate recorded outcomes. Upstream socket ResourceWarnings and a Windows gateway-cleanup permission message remain visible in raw logs; they were not suppressed. Notebook verification still returned exit code zero.

**Storage remains blocked:** Hadoop raises `HADOOP_HOME and hadoop.home.dir are unset` while invoking Windows `winutils.exe` for local permissions. The real Parquet write/read preflight has not succeeded. Preparation save/reload and persistent Bronze/Silver/Gold are not verified. No third-party Hadoop executables were installed. Alternatives are explicit approval of reviewed native Windows binaries or executing the unchanged Spark pipeline in a Linux environment; downloaded DLL/EXE files execute code with the user's permissions. The local Python 3.12 Spark worker uses the documented Apache SPARK-53759 socket-close backport; `setuptools` provides the required `distutils` compatibility import.

The outstanding scientific gate is approval of the exact target/completeness rule after reviewing these measured exclusions and biases. No model training is authorized or performed. The original Big Data rubric was not supplied, so exact rubric compliance remains unverified.
'''
    save('TASK1_TASK2_DISCUSSION.md', text)
    save('LABEL_FEASIBILITY.md', '# Label feasibility: measured, unapproved\n\n' + text[text.index('## Provisional y'):text.index('## Leakage prevention')] + '\nNo predictive training is authorized. Review the strict completeness rule and cohort selection before approving the label.\n')
    save('WHAT_CHANGED_IN_DATA.md', '# What changed in the data\n\n' + text[text.index('## Source counts'):text.index('## Temporal feasibility')] + '\nFull evidence and execution limits: [Task 1–2 discussion](TASK1_TASK2_DISCUSSION.md).\n')
    save('RUN_STATUS.md', f'''# GridRescue run status

Updated {now}. Current evidence: [Task 1–2 discussion](TASK1_TASK2_DISCUSSION.md).

## Completed and measured

- Canonical input relocation with original CSV hashes preserved; implementation directories retained.
- Python 3.12 project environment, PySpark 3.5.3 local worker compatibility backport, setuptools/distutils import repair.
- All-five-file CSV parser reconciliation: 122,019,012 data records; five headers explain the supplied total of 122,019,017.
- Complete 2018–2021 Spark integrity audit: 96,222,547 parsed rows; selected scopes have separate cleaning/feature/label reports.
- Prefix and selected-county in-memory audits; counts, examples, traces, missingness, gaps, outliers and feasibility statistics saved as JSON.

{nb_table}

## Still blocked or unverified

- Test suite: {test_summary}. See named error in `verification/tests.txt`; no all-green claim.
- Actual Parquet round-trip and preparation save/reload: missing Windows Hadoop native utilities. No third-party executable installation approved/performed.
- Complete-development deduplication, Silver/Gold/labels and full-population EDA: not run.
- Label approval and all Task 3 training, tuning, final testing: not authorized/performed. 2022 remains sealed from development.
- Exact original Big Data rubric compliance and dashboard interaction: unverified; outside the immediate deadline work.

The full analytical notebook outputs and persistence are distinct acceptance gates. Historical reports/logs are retained; report versions replaced during this refresh are backed up under `artifacts/report_history/`.
''')
    short=f'''# GridRescue: November 17 discussion summary

**Task 1 and Task 2 both executed from clean kernels in memory**, with saved tables, plots, interpretations and train-only preprocessing. This is analytical verification; persistent Spark artifacts remain blocked. The detailed evidence is [here](TASK1_TASK2_DISCUSSION.md).

**Data:** five unchanged CSVs now in `data/raw/`, with count field `customers_out` and five-character FIPS. Independent CSV parsing confirmed **122,019,012 data records**; five headers exactly reproduce the supplied 122,019,017 total. Complete 2018–2021 Spark parsing measured **96,222,547 development records**, including **6,618,821 invalid rows** under the strict rules. Flags overlap; most invalids are missing counts. Complete-development duplicates, features and labels were not computed. All annual files end on December 31 at 00:00 UTC, so that final day is incomplete.

**Actual analytical scopes:**

{counts_table}

The first scope is a January prefix smoke subset. The second retains all dates for Los Angeles, Miami-Dade and Harris. No missing observation became zero; no invalid outcome was imputed. Extreme valid counts remain, including a selected-county maximum of 455,986. Zero duplicates in these scopes does not prove zero duplicates in the population.

**X/y:** 13 current/past/calendar predictors with lag-missingness indicators. Exact timestamp lags and past-only rolling windows prevent future leakage. Candidate y tests an increase of max(200, 50% of current) within three hours and requires a positive current count plus all 12 future quarter-hour slots for either class. Incomplete windows remain unknown. No future audit field enters X. The target is still **unapproved**.

{split_table}

**Chronology and bias:** training 2018–2020, validation 2021, final test 2022 sealed. No test predictors/labels were generated. Real boundary-purge counts are zero because source years omit the last 23h45m; synthetic tests exercise crossing boundaries. Eligible positives are much more common in the well-covered county cohort than in prefixes. Neither scope is representative, and overlapping anchors are not independent events.

**Verified:** both notebook code-cell sequences (19 and 12 cells), source/path checks, in-memory cleaning/features/labels, Task 2 training-only medians/scaler and transformed feature checks. **Tests:** {test_summary}; remaining error(s): {', '.join(errors) or 'none'}.

**Blocked:** Parquet write/read and preprocessing save/reload require the missing Windows Hadoop utilities. No third-party Hadoop executables were installed. All Task 3 modeling remains gated; the original Big Data rubric is absent. No dashboard styling or model training was performed.
'''
    save('ONE_PAGE_DISCUSSION.md',short)
    save('FINAL_REPORT.md',short)
    print(json.dumps({'report': 'reports/TASK1_TASK2_DISCUSSION.md', 'tests': test_summary, 'notebooks': nb['notebooks']}, indent=2))


if __name__ == '__main__':
    main()

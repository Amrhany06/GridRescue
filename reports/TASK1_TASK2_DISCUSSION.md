# Task 1–2 discussion evidence

Generated 2026-11-16T21:30:35.368793+00:00. No Task 3 model was trained. Candidate labels remain **unapproved**. Analytical success and storage success are separate.

## What ran on which data

- **Complete development CSVs (2018–2021):** Spark FAILFAST parsing and aggregate integrity checks over **96,222,547 records**. No full-population deduplication, feature/label materialization or EDA is claimed.
- **Prefix debugging subset:** first 100,000 records per development year, 400,000 total; in-memory cleaning, duplicate/conflict reconciliation, gaps, outliers, past-only features and provisional label audit. Prefixes are not a random population sample.
- **Selected counties:** fixed FIPS 06037 (Los Angeles), 12086 (Miami-Dade), 48201 (Harris), selected before label inspection; all source dates in 2018–2021, 418,374 records. Same in-memory transformations and feasibility audit. These well-covered counties are geographic examples, not an approved modeling cohort.
- **2022:** integrity-only CSV record/shape count and prior byte/hash inventory. No quality distribution, predictors, labels, imputation, model development, tuning or scoring used 2022.

## Source counts and quality

| Year | Parsed records | Invalid rows (any reason) | Null count tokens | Off-grid timestamps | Valid before deduplication |
|---|---|---|---|---|---|
| 2018 | 21,776,806 | 2,041,717 | 2,027,828 | 15,473 | 19,735,089 |
| 2019 | 24,074,122 | 1,366,776 | 1,366,771 | 132 | 22,707,346 |
| 2020 | 25,545,517 | 2,105,233 | 2,101,520 | 3,747 | 23,440,284 |
| 2021 | 24,826,102 | 1,105,095 | 1,104,738 | 498 | 23,721,007 |

2022 has **25,796,465 parsed CSV data records**, verified with Python's CSV parser only. All five files contain **122,019,012 data records**. Adding five headers gives **122,019,017**, exactly the supplied inventory total. Every supplied annual total is also one higher than its parsed data count. This explains the arithmetic discrepancy; the upstream author's counting method was not independently verified.

The full development audit found no null FIPS/county/state/time tokens, malformed timestamps, invalid FIPS, or parsed timestamps outside the source year. Invalid-count totals equal missing-count totals in each year. Reason flags overlap, so null counts plus off-grid counts must not be summed as disjoint removals. Every annual source ends at **December 31 00:00 UTC**; the last calendar day is not fully covered. Source strings lack UTC offsets; UTC interpretation follows the supplied documentation.

## What happened to each row

Original CSV bytes are unchanged after relocation into `data/raw/`; hashes match the previous manifest. CSV tokens are read as strings so FIPS leading zeros survive. Counts must be nonnegative integer tokens fitting a signed 64-bit integer; identity/geography/time must be present, timestamps parse strictly, and observation times must lie on the quarter-hour grid. Invalid rows are quarantined, never imputed. Exact valid duplicate rows are removed once. All distinct variants of a conflicting county-time key are quarantined. The checked identity is raw = invalid + exact duplicate removals + conflict variants + Silver.

These are in-memory quarantine/Silver DataFrames; persistent Bronze, quarantine, Silver and Gold files have not been verified or claimed saved.

| Stage | Prefix smoke subset | Three counties, full development dates |
|---|---|---|
| raw | 400,000 | 418,374 |
| invalid | 66,369 | 1,434 |
| exact_duplicates_removed | 0 | 0 |
| conflict_rows | 0 | 0 |
| silver | 333,631 | 416,940 |

| Scope | Quarantine reason combination | Rows |
|---|---|---|
| Prefix | invalid_count | 66,369 |
| Counties | invalid_count | 1,336 |
| Counties | off_grid_timestamp | 98 |

Both real scopes had zero exact duplicates and zero conflicting-key variants. This does not establish full-population duplicate rates. Both in-memory runs assert Gold row count equals Silver. Missing county-time rows remain absent; no zeros, interpolation or new observations are inserted. County-year gap counts describe only observed endpoints, excluding unknown leading/trailing coverage. The selected counties have 2,688 missing internal quarter-hour slots across their county-years.

## Outliers and feature definitions

| Scope | Median | Q3 | IQR upper fence | Above fence | Maximum retained |
|---|---|---|---|---|---|
| Prefix | 5.0 | 41.0 | 99.5 | 51,859 | 22,952 |
| Counties | 254.0 | 798.0 | 1860.0 | 47,945 | 455,986 |

Quantiles use Spark approximate quantiles with relative rank tolerance 0.001. The IQR fence flags rarity, not invalidity; all valid extreme counts are retained. Capping/deletion could erase severe events. log1p is a display transform only.

X has **13 numeric predictors**: current count; exact same-county 15m/60m lags; current-minus-60m change; observed past-only [t−60m,t] mean/population variance; historical slot count (1–5); UTC hour/weekday/month; three missingness indicators. See [exact definitions](FEATURE_DEFINITIONS.md). IDs and geography remain audit/grouping metadata, so no categorical encoder is fitted. Missing lag/change predictors may receive training medians; missing observations and y never do. StandardScaler learns training mean/sample standard deviation only. Task 2's notebook reports the actual fitted values and transformed checks separately from saved artifacts.

| Scope | Year | Observed months | Hours | Weekdays | Missing exact 15m lag | Missing exact 60m lag |
|---|---|---|---|---|---|---|
| sample | 2018 | 1 | 24 | 2 | 8,084 | 23,531 |
| sample | 2019 | 1 | 24 | 2 | 5,427 | 16,631 |
| sample | 2020 | 1 | 24 | 2 | 5,195 | 16,020 |
| sample | 2021 | 1 | 24 | 2 | 6,491 | 20,270 |
| county | 2018 | 12 | 24 | 7 | 382 | 606 |
| county | 2019 | 12 | 24 | 7 | 267 | 389 |
| county | 2020 | 12 | 24 | 7 | 211 | 261 |
| county | 2021 | 12 | 24 | 7 | 178 | 297 |

Prefix training contains only January: month has zero training standard deviation and is scaled to zero. It does not validate seasonal effects. The selected-county audit actually observed all 12 months, 24 hours and seven weekdays in each year. Exact lags remain missing where the requested timestamp is absent; those missing counts are measured above, not inferred from row offsets. The historical slot count stayed within 1–5 in both scopes. The fitted in-memory preparation transformed **163,386 rows into 13-element vectors**, with 0 non-finite vectors and 0 dimension errors. Actual training medians, scaler means/std and constant predictors are saved as JSON statistics in `preparation_memory.json`; validation counts are in `preparation_validation.json`. These JSON files are evidence, not a persisted Spark pipeline.

## Provisional y, exclusions and splits

y=1 when a future reported count in (t,t+3h] reaches current + max(200, 50% of current). Current count must be positive. **Both classes require all 12 exact future quarter-hour slots**. Missing future observations remain unknown, even if a partial future trace contains a threshold crossing. Candidate labels are audit outcomes, not scientific approval.

| Scope | Split | Eligible | Positive | Negative | Unlabelled | Positive share among eligible |
|---|---|---|---|---|---|---|
| Prefix | train | 109,785 | 8,202 | 101,583 | 125,228 | 7.47% |
| Prefix | validation | 53,601 | 4,542 | 49,059 | 45,017 | 8.47% |
| Counties | train | 303,791 | 110,987 | 192,804 | 8,826 | 36.53% |
| Counties | validation | 102,449 | 33,719 | 68,730 | 1,874 | 32.91% |

| Scope | Unlabelled anchors | Complete windows with nonpositive anchor | Boundary-purged anchors |
|---|---|---|---|
| Prefix | 170,245 | 0 | 0 |
| Counties | 10,700 | 0 | 0 |

Training is 2018–2020; validation is 2021. The final 2022 test is sealed and **no test predictor/label rows are materialized**. An absent test row count here means unprocessed, not an empty final-test dataset. Horizon-crossing anchors would be purged; both real scopes have zero such anchors because source years end before the final three hours. Boundary behavior is exercised by the synthetic regression fixture, not a fabricated real example.

## Temporal feasibility and selection

| County / FIPS | Year | Observed days | Clean anchors | Eligible | Positive | Negative |
|---|---|---|---|---|---|---|
| Los Angeles / 06037 | 2018 | 365 | 34,254 | 32,580 | 14,063 | 18,517 |
| Miami-Dade / 12086 | 2018 | 365 | 34,673 | 33,686 | 10,863 | 22,823 |
| Harris / 48201 | 2018 | 365 | 34,644 | 33,535 | 11,209 | 22,326 |
| Los Angeles / 06037 | 2019 | 365 | 34,797 | 34,339 | 15,828 | 18,511 |
| Miami-Dade / 12086 | 2019 | 365 | 34,673 | 32,854 | 9,664 | 23,190 |
| Harris / 48201 | 2019 | 365 | 34,735 | 34,156 | 11,276 | 22,880 |
| Los Angeles / 06037 | 2020 | 366 | 35,011 | 34,773 | 15,799 | 18,974 |
| Miami-Dade / 12086 | 2020 | 366 | 34,925 | 34,047 | 10,338 | 23,709 |
| Harris / 48201 | 2020 | 366 | 34,905 | 33,821 | 11,947 | 21,874 |
| Los Angeles / 06037 | 2021 | 365 | 34,823 | 34,476 | 14,820 | 19,656 |
| Miami-Dade / 12086 | 2021 | 365 | 34,757 | 34,057 | 10,113 | 23,944 |
| Harris / 48201 | 2021 | 365 | 34,743 | 33,916 | 8,786 | 25,130 |

Each selected county has observations on every calendar date in each source year, including 366 dates in 2020; date presence does not imply every quarter-hour is present, and December 31 contains only the source endpoint. Both classes occur in every selected county-year. Eligible prevalence differs greatly from the January prefix subset. Coverage-based complete-case selection and the fixed populous counties can favor sustained, well-reported outages; neither cohort's prevalence generalizes to all counties. Future reporting completeness is unknown at inference time, so retrospective complete-case eligibility is not an operationally available prediction-time selector. Overlapping three-hour anchors are correlated and are not independent outage events.

Actual positive, negative and incomplete traces are in `reports/memory/{sample,county}/label_traces.json`. No real boundary example exists in either scope. Included-versus-all severity and county/state eligibility appear in each audit's `selection_bias` and `coverage_by_county_year` fields. These diagnostics do not justify changing the target or restricting the eventual modeling population without approval.

An independent standard-library check verified 18 exported traces against the exact expected timestamp set, source counts, threshold, maximum and candidate class; see `real_trace_checks.json`. Example: FIPS 01073 at 2018-01-01 00:00 UTC has current count 6, threshold 206, all 12 future slots, future maximum 242, and candidate y=1. Miami-Dade at the same anchor has current 658, threshold 987, future maximum 2,043 and all 12 slots, also candidate y=1.

## Leakage prevention and verification

Exact timestamp joins avoid mistaking four previous observations for one hour. Features use no future observations; mutation fixtures verify later measurements and other counties cannot alter an anchor's predictors. Future maxima, completeness, threshold and y are excluded from X. Chronological splitting and horizon purging prevent cross-partition outcome leakage. Preparation fits only eligible training rows and must be refitted inside each future CV fold. No target-based feature selection or 2022 tuning took place.

| Notebook | Status | Executed code cells |
|---|---|---|
| task1_eda | VERIFIED | 19 |
| task2_preprocessing | VERIFIED | 12 |

Notebook execution starts a fresh kernel for each notebook and saves outputs. See `notebook_execution.json` for the actual latest status. **Tests:** 19 tests executed: 18 passed; FAILED (errors=1); remaining error(s): test_preparation_fits_only_training_and_saves_reload. Details and exit codes are in `verification/tests.txt` and `verification/tests.json`. Dependency, syntax and layout checks have separate recorded outcomes. Upstream socket ResourceWarnings and a Windows gateway-cleanup permission message remain visible in raw logs; they were not suppressed. Notebook verification still returned exit code zero.

**Storage remains blocked:** Hadoop raises `HADOOP_HOME and hadoop.home.dir are unset` while invoking Windows `winutils.exe` for local permissions. The real Parquet write/read preflight has not succeeded. Preparation save/reload and persistent Bronze/Silver/Gold are not verified. No third-party Hadoop executables were installed. Alternatives are explicit approval of reviewed native Windows binaries or executing the unchanged Spark pipeline in a Linux environment; downloaded DLL/EXE files execute code with the user's permissions. The local Python 3.12 Spark worker uses the documented Apache SPARK-53759 socket-close backport; `setuptools` provides the required `distutils` compatibility import.

The outstanding scientific gate is approval of the exact target/completeness rule after reviewing these measured exclusions and biases. No model training is authorized or performed. The original Big Data rubric was not supplied, so exact rubric compliance remains unverified.

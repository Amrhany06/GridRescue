## Current verified state ? 2026-11-17T16:48:43.849687+00:00

Task 1/2 notebooks are ready for personal user review with executed Windows Arrow-local outputs. Native Hadoop writing remains blocked; full tests 40/41 passed with the original native integration error unchanged. See `TASK1_TASK2_CHANGE_SUMMARY.md`, `WINDOWS_SPARK_DIAGNOSIS.md`, `TASK1_TASK2_RUBRIC_REVIEW.md` and `NOTEBOOK_REVIEW_GUIDE.md`. Task 3 remains paused, 2022 sealed for modeling, Linux retained. Older execution statements below are historical and superseded by this verified update.

---

# What changed in the data

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


Full evidence and execution limits: [Task 1–2 discussion](TASK1_TASK2_DISCUSSION.md).

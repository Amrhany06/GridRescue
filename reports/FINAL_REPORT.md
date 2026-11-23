# GridRescue: November 17 discussion summary

**Task 1 and Task 2 both executed from clean kernels in memory**, with saved tables, plots, interpretations and train-only preprocessing. This is analytical verification; persistent Spark artifacts remain blocked. The detailed evidence is [here](TASK1_TASK2_DISCUSSION.md).

**Data:** five unchanged CSVs now in `data/raw/`, with count field `customers_out` and five-character FIPS. Independent CSV parsing confirmed **122,019,012 data records**; five headers exactly reproduce the supplied 122,019,017 total. Complete 2018–2021 Spark parsing measured **96,222,547 development records**, including **6,618,821 invalid rows** under the strict rules. Flags overlap; most invalids are missing counts. Complete-development duplicates, features and labels were not computed. All annual files end on December 31 at 00:00 UTC, so that final day is incomplete.

**Actual analytical scopes:**

| Stage | Prefix smoke subset | Three counties, full development dates |
|---|---|---|
| raw | 400,000 | 418,374 |
| invalid | 66,369 | 1,434 |
| exact_duplicates_removed | 0 | 0 |
| conflict_rows | 0 | 0 |
| silver | 333,631 | 416,940 |

The first scope is a January prefix smoke subset. The second retains all dates for Los Angeles, Miami-Dade and Harris. No missing observation became zero; no invalid outcome was imputed. Extreme valid counts remain, including a selected-county maximum of 455,986. Zero duplicates in these scopes does not prove zero duplicates in the population.

**X/y:** 13 current/past/calendar predictors with lag-missingness indicators. Exact timestamp lags and past-only rolling windows prevent future leakage. Candidate y tests an increase of max(200, 50% of current) within three hours and requires a positive current count plus all 12 future quarter-hour slots for either class. Incomplete windows remain unknown. No future audit field enters X. The target is still **unapproved**.

| Scope | Split | Eligible | Positive | Negative | Unlabelled | Positive share among eligible |
|---|---|---|---|---|---|---|
| Prefix | train | 109,785 | 8,202 | 101,583 | 125,228 | 7.47% |
| Prefix | validation | 53,601 | 4,542 | 49,059 | 45,017 | 8.47% |
| Counties | train | 303,791 | 110,987 | 192,804 | 8,826 | 36.53% |
| Counties | validation | 102,449 | 33,719 | 68,730 | 1,874 | 32.91% |

**Chronology and bias:** training 2018–2020, validation 2021, final test 2022 sealed. No test predictors/labels were generated. Real boundary-purge counts are zero because source years omit the last 23h45m; synthetic tests exercise crossing boundaries. Eligible positives are much more common in the well-covered county cohort than in prefixes. Neither scope is representative, and overlapping anchors are not independent events.

**Verified:** both notebook code-cell sequences (19 and 12 cells), source/path checks, in-memory cleaning/features/labels, Task 2 training-only medians/scaler and transformed feature checks. **Tests:** 19 tests executed: 18 passed; FAILED (errors=1); remaining error(s): test_preparation_fits_only_training_and_saves_reload.

**Blocked:** Parquet write/read and preprocessing save/reload require the missing Windows Hadoop utilities. No third-party Hadoop executables were installed. All Task 3 modeling remains gated; the original Big Data rubric is absent. No dashboard styling or model training was performed.

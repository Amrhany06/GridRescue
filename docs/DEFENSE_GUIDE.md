# GridRescue discussion defense guide

Start with the [completion audit](../reports/NOTEBOOK_COMPLETION_AUDIT.md) for the current run and the [code walkthrough](CODE_WALKTHROUGH.md) for the TA discussion. Earlier reports document how the project reached this point.

## Opening statement

GridRescue studies historical EAGLE-I county electricity outage reports. The approved three-county experiment predicts whether a positive reported outage count materially escalates within three hours. Task 1 explores reporting and cleaning. Task 2 prepares the past-only predictors and eligible outcomes. Task 3 compares three classifiers using 2018–2021 development data. The 2022 evaluation is a separate approval gate.

## Evidence to open during the discussion

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| `reports/source_manifest.json` | Actual filenames, measured bytes, headers and explicitly recorded scan status | Published row totals do not prove local row counts |
| `reports/audit.json` when present | Measured execution-scope cleaning and eligibility counts | A subset result does not describe all five files |
| `reports/WHAT_CHANGED_IN_DATA.md` | Raw-to-clean-to-eligible reconciliation for the named scope | Excluded rows are not proven zero-outage periods |
| `reports/LABEL_FEASIBILITY.md` | Future-window completeness, provisional class counts and examples | Scientific approval or population representativeness |
| `notebooks/task1_eda.ipynb` | Read Data through Final Summary outputs | Unexecuted cells are not results |
| `notebooks/task2_preprocessing.ipynb` | Feature definitions, chronological splits and preprocessing outputs | No model training belongs in Task 2 |
| `notebooks/task3_modeling.ipynb` | Real development training, model comparison, error analysis, explanations and artifact reload | Final held-out performance remains pending |
| `src/gridrescue/pipeline.py` | Implementation of cleaning and temporal transformations | Source code alone does not establish successful execution |

Use measured counts from the latest executed outputs. The official ML PDFs and Big Data DOCX are available under `docs/requirements/`.

## What is actually on disk?

Initial inspection found five CSVs at the project root. They were subsequently moved without changing their bytes into `data/raw/`, with hashes verified. All five headers are `fips_code, county, state, customers_out, run_start_time`. The actual count column is `customers_out`; `sum` in the master narrative is not the observed local header.

One row is a reported county/timestamp customer-outage count. It is neither a single outage event nor a power or energy measurement. `01015` is a county identifier, not a numeric magnitude. The first inspected 2018 record reports Calhoun, Alabama, one customer out at `2018-01-01 00:00:00`. The strings do not themselves include a timezone suffix: UTC treatment is an explicit source-contract assumption that the pipeline must make visible.

The manifest records byte sizes of 999,210,542; 1,102,778,792; 1,170,699,724; 1,141,058,232; and 1,187,596,176 for 2018 through 2022. Bytes are storage size, not DataFrame memory. CSV parsing confirmed **122,019,012 data records**; adding five headers exactly reproduces the supplied 122,019,017 total. The upstream author's counting method was not independently verified. Spark independently parsed all **96,222,547 development records** and measured integrity flags. Full deduplication/features/labels were not run on that population. The prefix subset has 400,000 raw rows; the three selected counties have 418,374 raw rows across complete source date ranges. Neither is a representative population sample. 2022 received integrity counting only.

The Windows environment uses Python 3.12.14, Java 17 and PySpark 3.5.3 with the documented project-local worker backport. Task 2 uses the verified Arrow-local Parquet and Spark preparation reload. The native Hadoop writer still fails in this environment. See the completion audit for the current notebook and test results.

## Explain the transformations

1. **Read and preserve:** retain source strings and original files, preserve five-character FIPS, parse timestamps under a documented UTC contract, and measure source nulls before typed transformations.
2. **Validate:** count malformed identifiers, missing/unparseable timestamps, nonintegral or negative customer counts, and any off-grid observations. Quarantine with reason codes; do not make invalid data look valid through coercion.
3. **Deduplicate:** exact repeated source records differ from county-time keys with conflicting values. Report both. Follow the executed policy in `WHAT_CHANGED_IN_DATA.md`, including whether every conflicting key was quarantined.
4. **Measure gaps:** count observed intervals longer than 15 minutes and absent expected slots. A gap is not a null inside a row and is not a zero. Missing-row diagnostics describe observational coverage.
5. **Explore:** use Spark aggregates and bounded plots. Inspect severe values before treatment. A large hurricane-era outage can be real; an IQR flag is not evidence of error. Show actual retained/transformed choices, never claim an unrun sensitivity analysis.
6. **Generate features:** match lags by county and exact timestamp; compute historical rolling statistics in a time-range window ending at the anchor, with completeness information. Derive UTC calendar features.
7. **Audit the candidate target:** inspect the 12 expected future quarter-hour slots in `(t,t+3h]`. Distinguish verified events, complete no-event windows, incomplete unknown windows and split-boundary exclusions. Follow the implementation's conservative eligibility rule; never infer a negative from absence.
8. **Split and prepare:** proposed training 2018-2020, validation 2021, final held-out 2022; purge anchors whose target horizon crosses partition boundaries. Fit learned imputation/scaling/encoding on training only. No model fitting occurs in Task 2.

At each stage, explain which rows leave and why. In particular, fewer eligible examples can reflect coverage restrictions, not a cleaning improvement.

In `src/gridrescue/pipeline.py`, `read_source` validates headers, `clean` reconciles row dispositions, `features` computes historical windows and exact lags, and `audit_labels` applies the 12-slot rule and chronological tags. `fit_preparation` fits only training rows. Task 2 uses persistent Arrow-local artifacts with fresh-kernel checks. `scripts/run_pipeline.py --audit-only` also supports an in-memory run with JSON evidence.

The inspected predictor allowlist is `customers_out_t`, `lag_15m`, `lag_60m`, `delta_60m`, `rolling_mean_60m`, `rolling_variance_60m`, `history_slots_60m`, `hour_utc`, `weekday_utc`, `month_utc`; orchestration adds missingness flags for the two lags and change. The inclusive historical interval `[t-60m,t]` has five expected quarter-hour slots, not four. Spark's inspected weekday extraction uses its `dayofweek` convention; verify the installed API and emitted values before interpreting numeric weekday codes. No categorical predictor is selected in this baseline allowlist, so absent one-hot encoding must be explained as a design choice rather than an executed transformation.

## X, y and scientific limitations

Candidate `X` contains known-at-anchor quantities: current reported count, exact-time lags, past changes, historical rolling statistics and UTC calendar features. County identifiers support grouping and traceability; treating their numeric digits as magnitude is meaningless. Unverified customer denominators, future maxima and retrospective metadata are excluded from predictors.

`candidate_y` asks whether an observed future count reaches `current + max(200, 0.5 * current)` in the next three hours. For example, a current count of 500 yields a threshold of 750. The approved threshold defines the research outcome. A change to the objective requires separate approval.

Sparse reporting can select sustained, well-covered outages into the labelled population. Report eligibility and class counts by county/year; compare included and excluded current-count distributions. A model trained on eligible windows estimates conditional escalation in that selected population. It does not predict every new blackout, physical equipment failure, restoration time, or live grid state.

## Concepts to explain precisely

| Pair or concept | Explanation tied to GridRescue |
|---|---|
| Time series / sequential / panel | A county is a timestamp-indexed series; ordered records are sequential; many counties over time form panel data |
| Analysis / forecasting | EDA describes the historical record; a future escalation class is a forecasting task |
| Classification / regression | A future yes/no event is classification; a future numerical count would be regression and requires a separately approved objective |
| Extraction / generation / selection | Extract hour from time; generate a past-change feature; select a justified subset of candidates |
| Sequential feature selection | Iteratively add/remove predictors using development validation; it is not the same as using sequential data and is not claimed executed |
| Imputation / zero filling | A train-learned replacement for a missing predictor is distinct from inventing a county-time source observation |
| Standardization / normalization | Standardization uses training mean and scale; unit-norm normalization scales each feature vector; explain the convention used |
| Min-max scaling | Uses training extrema; later values may fall outside zero to one |
| Fit / transform | Fit learns preprocessing statistics; transform applies already-frozen statistics |
| Parameters / hyperparameters | Coefficients are learned parameters; regularization and tree depth are externally chosen hyperparameters |
| Transformations / actions | Spark `select`, `filter`, joins and windows build lazy plans; `count`, `show` and writes execute them |
| Window / partition | A window defines per-county temporal context; physical partitions divide execution and can require costly shuffles |
| Metadata join | Use a justified, unique lookup with explicit availability assumptions; verify join cardinality so rows are not multiplied |
| CSV / Parquet | CSV stores text; Parquet stores typed compressed columns. A claim about speed requires the logged identical-query benchmark |
| Local Spark / cluster | Local-mode Spark demonstrates its execution API, not multi-machine deployment |

## Leakage examples and proofs to show

| Failure | Why wrong | Evidence to request |
|---|---|---|
| `lag(count,4)` called one hour ago | Four observed rows can span gaps | Exact-time lag fixture with a missing quarter hour |
| Centered rolling mean | Includes future values | Future-value mutation must leave anchor predictors unchanged |
| Future maximum in `X` | Directly exposes outcome | Explicit predictor allowlist separate from target diagnostics |
| Random train/test rows | Nearby outage observations share information | Chronological timestamps and horizon purge checks |
| Scaler fitted to all years | Learns held-out distributions | Train-only fit test with extreme validation values |
| Missing future row called negative | Assumes an unobserved outcome | Incomplete-window fixture remains ineligible/unknown |
| Choosing threshold with 2022 outcomes | Tunes on final test | Sealed test policy and development-only execution scope |

## Hard TA questions: concise honest answers

1. **Why this dataset?** It contains repeated county-level outage observations suited to a meaningful temporal risk question and Spark processing. Its sparse reporting limits what can be inferred.
2. **How many rows do you have?** Read the measured scope and count in the latest manifest/audit. Do not substitute the published 122M total or a notebook subset count for a full local count.
3. **What does one row mean?** A reported county-time customer count, not a physical event, number of households, or kWh.
4. **What is the real count column?** The inspected local files use `customers_out`; the narrative's `sum` is not their header.
5. **How did you preserve leading zeros?** FIPS is a string; inspect the `01015` sample and the identifier regression test.
6. **How do you know timestamps are UTC?** That is the documented source convention; source strings lack offsets. The session timezone must be set explicitly, and the assumption is disclosed.
7. **Why not fill missing observations with zero?** Absence can mean no reported outage or missing reporting. These alternatives cannot be resolved from the row alone.
8. **What did cleaning remove?** Show actual reconciliation by invalid rows, exact duplicates and conflicting keys. A generic percentage is not evidence.
9. **Are all duplicate keys duplicates?** No. Identical repeated records and conflicting measurements at the same intended key need separate audits and policies.
10. **Why retain extreme counts?** Statistical rarity does not establish measurement error; severe real events are part of the problem. Show executed diagnostics and treatment.
11. **What exactly are you predicting?** Material reported escalation within three hours, conditional on a positive current report and a complete outcome window.
12. **Why 200 customers or 50 percent?** The absolute floor requires a material increase at lower counts. The relative component requires bigger changes at higher counts. These parameters are fixed in the approved classroom experiment.
13. **How do you label a missing future window?** Never infer negative from absence. Follow the audited completeness rule and preserve unknown or excluded status.
14. **Can you trust a positive with incomplete coverage?** An observed threshold crossing proves an observed event, but including partial positives while requiring complete negatives can create selection bias. Use the audited conservative rule and request approval before changing it.
15. **What is a 60-minute lag?** The same county at exactly `t-60m`; if absent, the lag is missing even if four previous rows exist.
16. **Does your rolling mean assume regular data?** It uses an actual timestamp range and available observations, and reports coverage. It must not masquerade as a complete regularly sampled history.
17. **Why a chronological split?** The intended deployment predicts future periods. Random rows can mix nearby observations from the same outage episode across partitions.
18. **Why purge boundary rows?** A training label must not inspect future outcomes belonging to validation or final test.
19. **What did you scale and when?** Read the saved preparation artifact and Task 2 output. Only training data can learn statistics; no unexecuted preprocessing is claimed.
20. **Why not use county FIPS as a number?** Digits are administrative identifiers without an ordered physical distance. It is useful for grouping, not a numeric magnitude predictor.
21. **How is your sample representative?** A computational smoke subset need not be representative. State its exact selection rule and scope; do not generalize its prevalence or extremes to all years/counties.
22. **Which models performed best?** None is claimed trained before target approval. The planned comparison uses logistic regression, random forest and histogram gradient boosting on one common target.
23. **Why accuracy is insufficient?** Rare positives allow a majority-negative rule to have high accuracy. Report prevalence, precision, recall, F1, confusion matrix and PR-based metrics after legitimate evaluation.
24. **What does CV mean?** Cross-validation here uses forward chronological folds; computer vision is a different field and is not part of this project.
25. **What did Spark actually do?** Point to executed filters, grouped aggregates, timestamp windows, joins and Parquet round-trip evidence. Merely importing Spark proves none of these.
26. **Is the dashboard live monitoring?** No. It displays compact historical exports and only validated model outputs if such outputs exist.
27. **Where is the Big Data rubric?** The original was not located initially; requirements in the explainer are a secondary summary. Exact original-rubric compliance remains unverified.
28. **What would invalidate your conclusion?** Weak coverage, changes in reporting, selected eligible windows, chronology leakage, unapproved label semantics, or poor later-period generalization. Show limitations rather than hiding them.

## Teach-back rehearsal

Open the current reports and notebooks. Explain aloud, without reading a memorized number:

1. One real record, every source column, the measured execution scope and where the count came from.
2. A null, a missing row, an exact duplicate and a conflicting key, and what the code actually did to each.
3. One actual plot, its units, an observation supported by it and a claim it cannot support.
4. An exact-time lag, a historical window and why changing tomorrow's values cannot change today's predictors.
5. Positive, negative, incomplete and split-boundary audit examples; identify any category absent from the sampled data.
6. Every learned preprocessing statistic, which rows fitted it, and what remains blocked.
7. Why 2022 cannot choose features, target thresholds, algorithm settings or the winning model.

If you cannot demonstrate a step in executed output, describe it as planned or blocked. This is a defensible answer; an invented result is not.

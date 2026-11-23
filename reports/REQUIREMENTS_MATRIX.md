## Current verified state ? 2026-11-17T16:48:43.849687+00:00

Task 1/2 notebooks are ready for personal user review with executed Windows Arrow-local outputs. Native Hadoop writing remains blocked; full tests 40/41 passed with the original native integration error unchanged. See `TASK1_TASK2_CHANGE_SUMMARY.md`, `WINDOWS_SPARK_DIAGNOSIS.md`, `TASK1_TASK2_RUBRIC_REVIEW.md` and `NOTEBOOK_REVIEW_GUIDE.md`. Task 3 remains paused, 2022 sealed for modeling, Linux retained. Older execution statements below are historical and superseded by this verified update.

---

﻿# Requirements traceability and source inventory

Inspected 2026-11-16. This matrix records requirements, not completion claims. Execution evidence belongs in RUN_STATUS.md and generated audit outputs.

Current execution: Task 1 and Task 2 analytical cells completed from clean kernels in memory. Task 2's persistent **Save Preparation** criterion remains blocked, as do Parquet write/read and the preparation save/reload integration test. Actual scope, outputs, interpretations and remaining limits are in `TASK1_TASK2_DISCUSSION.md`; successful notebook execution is not a claim that every storage/rubric criterion is satisfied.

## Files actually present

- Three original ML PDFs are now in `docs/requirements/`: `Task 1 for ML (1).pdf` (2 pages), `Task 2 for ML.pdf` (1 page), `Task 3 for ML.pdf` (2 pages). All five pages were extracted with pypdf and read; matching UTF-8 `.txt` transcriptions remain there. Original contents are unchanged.
- The master prompt is now at root as `GridRescue_Codex_Copy_Paste_Prompt.md`; the explanation is `docs/GridRescue_Complete_Project_Explained.md`. The checklist and other kit references remain in `GridRescue_Complete_Explainer_And_Codex_Kit (2)/`.
- The five original CSVs are now in `data/raw/`. `reports/layout_migration.json` records relocation and verified original hashes. The implementation, reports and notebooks were retained.
- **BLOCKED: original Big Data rubric / requirements screenshot is absent.** The explanation refers to a user-supplied screenshot, but the local inventory contains no such image or separate Big Data rubric. The explanation's Big Data summary can guide implementation but cannot establish exact rubric compliance or point weights. Request that original only for final rubric verification; continue routine work.
- **UNAVAILABLE:** separate old handbook and `GridRescue_Full_Concept_Table.md` were not found. The supplied complete explanation is available; do not claim to have read absent material.
- No repository AGENTS.md was found in initial recursive inventory; user-supplied global instructions govern.

## Task 1: Data Preparation & Exploration

| Exact PDF requirement | Planned evidence / acceptance criterion |
|---|---|
| Explore before changing values | Read Data source section precedes cleaning and shows actual schema/sample. |
| Read Data | Explicit-schema Spark read; source names and headers recorded. |
| Random Sample Data | Reproducible random actual rows; distinguish sample selection scope from random display. |
| Size of Data | Measured row and column counts, clearly scoped; published totals labeled separately. |
| Information of Data | Data types, non-null counts, memory usage. For Spark report stored bytes and explain these are not in-memory usage; avoid presenting byte size as RAM. |
| Check Names of Columns | Actual names and meanings, including any mismatch with planned `sum` name. |
| Check Description | Descriptive statistics for relevant fields. |
| Number of Unique Values | Unique counts in each column; explain ID/high-cardinality columns. |
| Check Balance of Data | Provisional eligible label balance only; approved classification not yet assumed. |
| Missing Values | Existing-row nulls, explicit handling and reasons; separately report missing county-time rows. |
| Duplicate Rows | Exact duplicates versus conflicting county-time keys, policies and reconciled counts. |
| Outlier Detection | Appropriate statistics and plots identify candidates. |
| Outlier Treatment Techniques | Compare keep/cap/transform/remove; justify retention of plausible real disasters rather than automatic deletion. |
| Univariate Analysis | Distribution, central tendency, spread and unusual patterns with actual table/plot interpretation. |
| Feature vs. Target Analysis | Associations only for defensible provisional labels, clearly flagged; otherwise explicit scientific block. |
| Feature-to-Feature Analysis | Predictor relationships and overlap/interactions; no numerical interpretation of FIPS magnitude. |
| Correlation Analysis | Suitable numerical correlations and visualization; direction/strength and limits interpreted. |
| GroupBy / Statistical Summary Analysis | Counts/means/medians or other appropriate statistics by relevant categories. |
| Submission checklist | Notebook follows sections/subsections, includes executable code, actual output/plots, short observations, all cleaning/outlier reasons and concise final findings. |

## Task 2: Feature Engineering & Data Preprocessing

The PDF explicitly says **stop before selecting or training any model**.

| Exact PDF requirement | Planned evidence / acceptance criterion |
|---|---|
| Identify Features | Candidate predictors/types; IDs and leakage flagged. |
| Create Features | Safe date parts, exact-time historical features; no target used in predictors. |
| Review Changes | Table of features added/changed/removed and reasons. |
| Define Inputs | Explicit X feature list; provisional y formula and eligibility separated from X. |
| Split the Data | Training 2018-2020, validation 2021, untouched test 2022; chronological and horizon-purged. |
| Avoid Leakage | Learned imputation/scaling/encoding and target-based selection fitted only on training; testing evidence. |
| Missing Values | Predictor imputation justified; never invent observations or impute y. |
| Categorical Encoding | Appropriate encoding if selected categoricals exist; otherwise explain omission. |
| Feature Scaling | Standardization or normalization where needed; fitted training statistics and transformation examples. |
| Check Outputs | Actual processed shape and example rows. |
| Validate Features | Invalid/null checks and consistent feature columns across splits. |
| Save Preparation | Processed data, feature metadata and fitted preprocessing available for Task 3; no trained estimator. |

The PDF's clustering note is conditional guidance, **not authorization to replace the project's target with clustering**.

## Task 3: Model Research, Validation & Comparison

This phase is gated on user authorization of a scientifically defensible target; no fabricated labels or scores. Models requested by master prompt are LogisticRegression, RandomForestClassifier and HistGradientBoostingClassifier.

| Exact PDF section | Required evidence after label approval |
|---|---|
| 01 Model Research & Selection | Identify learning problem and main metric; three different algorithms; table with rationale, mechanism, strengths/limitations, key hyperparameters and references. |
| 02 Build Pipelines & Default Baselines | Same feature definitions, appropriate transforms and reproducible estimator pipelines; defaults first (only essential settings such as random_state changed); settings, fit time, validation metrics, predictions retained; refit preprocessing inside each CV training fold. |
| 03 Pre-Validation & Cross-Validation | Untouched test, appropriate group/time-aware folds, identical strategy for all models; main metric mean +/- standard deviation; training-versus-validation results and generalization diagnosis. |
| 04 Hyperparameter Tuning | Small justified search space, training-only search, default-versus-tuned comparison using same evaluation criteria; no held-out-test tuning. |
| 05 Metrics & Diagnostic Results | Classification accuracy, precision, recall, F1, confusion matrix, ROC-AUC where meaningful, imbalance explanation; master prompt adds PR-AUC and prevalence. |
| 06 Compare & Select Best Model | Comparison table of default/tuned settings, main/supporting metrics and fit time; explain stability and complexity; winner based on development validation only. |
| 07 Final Evaluation, Save & Reload | Refit on allowed training data, single final untouched test evaluation, complete preprocessing+model artifact plus features/parameters/metrics; fresh-cell reload and inference demonstration. |
| Submission Checklist | Runnable notebook, research and three pipelines, baseline/CV/tuning outputs and plots, justified comparison/winner/final results, saved artifacts and reload proof. |

Regression and clustering clauses in the rubric describe alternatives for other tasks. This project's fallback requires explicit approval; they are not authority to switch objectives.

## Master prompt additions and scientific constraints

- Phase 0: actual inventory, bytes, headers, source samples, five-character FIPS, UTC interpretation, nonnegative integral counts, Python/Java/PySpark check; SparkSession plus real Parquet round trip. Save source_manifest.json and VERIFIED / UNVERIFIED / BLOCKED status. Published 122,019,017 rows is never a local measurement without counting.
- Source -> Bronze -> Silver -> Gold, small real scope before full data; reusable code and source preservation. Audit invalids/nulls/exact duplicates/conflicts/gaps/extremes with row reconciliation; no full-data pandas collection and no absent-row zero filling.
- Provisional target: current observed outage escalates by at least max(200, 50% of current customers out) within next three hours. Audit expected future slots, observed count/gaps, county/year eligibility, class balance, selection bias and manually inspectable positive/negative/incomplete/boundary examples. Incomplete windows cannot become assumed negatives. Seek approval before training or changing definition.
- Exact-timestamp lags; timestamp-based past-only rolling mean/variance/change; UTC calendar variables; explicit feature disposition table. Purge labels crossing split boundaries. Do not use 2022 to choose thresholds, features, cleaning hyperparameters or models.
- Save WHAT_CHANGED_IN_DATA.md and LABEL_FEASIBILITY.md with actual raw/clean/eligible/train/validation/test reconciliation; distinguish prepared artifacts from authorized supervised readiness.
- November 17 priority: Task 1/2 executable and explainable. ONE_PAGE_DISCUSSION.md plus DEFENSE_GUIDE.md with 20 hard TA questions, teach-back prompts, measured findings and code/cell references.
- November 21 Task 3; no deep learning/computer vision. No model-score invention or claim of live monitoring.
- Tests: FIPS, gaps versus nulls, exact/conflicting keys, reconciliation, exact-time lags, eligibility, future leakage, split purge, train-only fit; model save/reload only if a model is trained.

## Big Data: provisional mapping from supplied explanation only

| Supplied explanation requirement | Evidence to produce |
|---|---|
| Data collection and provenance | Manifest, source attribution/link, preserved sources. |
| Cleaning and EDA | Actual audits, counts, transformations, plots and defensible decisions. |
| Meaningful PySpark work | Executed filter, groupBy/agg, temporal windows and justified metadata join without row amplification. |
| Storage/processing comparison | One identical CSV-versus-Parquet query; actual timings, scope and cache/order limitations. |
| Project-specific analysis | Conditional escalation feasibility and historical outage observations; no unapproved inference claims. |
| Interactive dashboard | Streamlit on compact real exports: title/explanation, KPIs, state/county/date/severity filters, trends, findings, quality caveats; scores only if validated. |
| Final deliverables | Runnable code/notebooks, data-source link, working app, concise problem/data/method/results/conclusion report, demo and README setup/run commands. |

Original Big Data rubric verification remains BLOCKED until the absent source is supplied. Nothing in this mapping invents rubric weights or exact grading wording.

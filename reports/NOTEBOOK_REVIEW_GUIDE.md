# Task 1 and Task 2 — notebook review guide

Open the executed notebooks in Jupyter or VS Code and follow the navigation table at the top. All changed/new code has been executed from a clean kernel. Every count below refers to its displayed scope. Task 3 remains PAUSED until the user approves these notebooks.

Spark performs parsing, cleaning, joins, windows, aggregation and fitted preparation. pandas is used only for bounded examples and compact plotting/export tables. Arrow-local performs local storage encoding; it does not replace Spark processing.

## Task 1

| Section / cell ID | Responsible implementation | Key displayed evidence | Defense question |
|---|---|---|---|
| Read Data / original columns / `task1_eda-003` | `pipeline.read_source` | Five-column schema; bounded raw table | Why keep FIPS and invalid tokens as strings? |
| Random Sample Data / `task1_eda-005` | `Spark rand/orderBy` | Ten actual prefix rows | Why is this not a random national sample? |
| Size / scope / source coverage / `task1_eda-scope-ledger` | `Previously executed full_source_audit; inventory` | Full-development integrity table and three-scope ledger | What exactly explains the five-row discrepancy? |
| Types, non-null counts and memory / `task1_eda-009` | `Spark aggregation; psutil` | Schema and distinct memory measurements | Why are file bytes, Python RSS and JVM cache different? |
| Names / description / unique values / `task1_eda-015` | `Spark describe/countDistinct` | Original column meanings; summary statistics | Why is a county code not a magnitude predictor? |
| Class balance / `task1_eda-017` | `pipeline.audit_labels` | Complete, incomplete, positive and negative counts | Why can an incomplete window not become class 0? |
| Missing / invalid / cleaning impact / `task1_eda-quarantine` | `pipeline.clean; storage.read_frame` | Actual rejected rows, reasons and disjoint removal ledger | Which rows were removed at each stage? Why not zero-fill? |
| Exact duplicates versus key conflicts / `task1_eda-021` | `pipeline.clean` | Reconciliation, uniqueness assertion and actual implementation | Why quarantine all conflicting variants instead of taking the first? |
| Outlier Detection / Treatment / `task1_eda-025` | `Spark approxQuantile; display-only log1p` | IQR fence, real extremes, box/histogram and treatment comparison | Does exceeding the IQR fence prove an error? |
| Univariate Analysis / `task1_eda-027` | `Spark aggregation; bounded plotting` | Outage-size distribution and UTC-hour coverage | Does a row count equal affected people or outage events? |
| Feature versus Target / `task1_eda-029` | `Spark grouped means` | Measured class-conditional severity and past change | How does the target definition affect these associations? |
| Feature-to-Feature / Correlation / `task1_eda-033` | `pipeline.features; bounded correlation` | Scatterplots and pairwise-complete Pearson matrix | What do skew and missing pairs do to interpretation? |
| GroupBy / Statistical Summaries / `task1_eda-035` | `Spark groupBy/agg` | State observation coverage and severity summaries | Are these comparisons nationally representative? |
| Full-year county context / `task1_eda-county-context` | `dashboard_data.load_scope; verified Spark daily exports` | Monthly county severity beside observation coverage | Why compare coverage alongside severity? |
| Final findings / decisions / `task1_eda-037` | `Measured audit reports` | Concise counts, policies and scope limitations | Which findings are national integrity facts and which are subset EDA? |

## Task 2

| Section / cell ID | Responsible implementation | Key displayed evidence | Defense question |
|---|---|---|---|
| Identify Features / `task2_preprocessing-feature-dictionary` | `pipeline.PREDICTORS / features` | Exact ordered thirteen-feature dictionary | What is available at prediction time? Which columns are excluded? |
| Create / Review Features / `task2_preprocessing-005` | `pipeline.features` | Actual feature rows and shared implementation source | What are transformations, actions, joins and windows doing? |
| Exact lag / rolling / missing indicators / `task2_preprocessing-manual-window` | `pipeline.features; independent bounded arithmetic` | Five real history rows, exact lags, mean/variance and missing-lag rows | Why are four previous reports not necessarily one hour? |
| Define X and approved y / `task2_preprocessing-009` | `pipeline.audit_labels` | Input allowlist and class/completeness table | State the exact threshold and twelve-slot completeness rule. |
| Positive / negative / incomplete examples / `task2_preprocessing-011` | `pipeline.audit_labels; expected-time comparison` | Actual trajectories and missing expected quarter-hours | Why does even a partially observed positive remain excluded? |
| Eligibility and selection impact / `task2_preprocessing-eligibility-stages` | `Spark conditional aggregation` | Nested counts for both scopes and exclusions | Why must nested stage counts not be summed as removals? |
| Chronological Split / Avoid Leakage / `task2_preprocessing-014` | `pipeline.split_tag / audit_labels` | Train/validation counts and boundary assertions | How do past-only X, purged horizons and fold-only fitting prevent leakage? |
| Missing Values / Categorical Encoding / `task2_preprocessing-017` | `pipeline.fit_preparation` | Loaded genuine Spark stages; numeric-only decision | Does predictor imputation invent missing observations or labels? |
| Scaling and fitted training statistics / `task2_preprocessing-scaling-example` | `Spark ImputerModel / StandardScalerModel` | Thirteen fitted medians/means/sample stds and real before/after values | Why fit only training? What happens to a zero-variance predictor? |
| Three-county Task 2 summary / `task2_preprocessing-county-summary` | `Verified county audit, fitted JSON and persistence report` | Separate train/validation counts, prevalence, eligible predictor nulls and all thirteen training statistics | Why do these statistics differ from the January-prefix examples? |
| Check Outputs / Validate Features / `task2_preprocessing-021` | `PipelineModel.transform; vector_to_array` | Bounded rows/vectors; dimensions, class/split sizes and finite checks | What does each position in the final vector represent? |
| Save Preparation / Reload / `task2_preprocessing-023` | `storage.write_frame / read_frame / save_preparation / load_preparation` | Two-scope fresh-process parity summary and artifact paths | Why is Arrow-local a workaround rather than a native Hadoop repair? |

## Scope and storage contract

Full-source auditing establishes inventory and development integrity only. Prefix EDA uses the first 100,000 rows of each development year; the selected-county cohort uses all available 2018–2021 dates for three fixed counties. Neither is nationally representative. The 2022 inventory count is historical integrity metadata, not held-out feature/label access.

Read `WINDOWS_SPARK_DIAGNOSIS.md` and `persistence_validation.json` for exact schema/null/value/statistic parity, memory bounds, version coupling and the remaining native blocker. Previous executed Windows notebooks remain in `artifacts/windows_notebooks/`; the pre-recovery checkpoint is recorded in `windows_recovery_checkpoint.json`.

Reproduce without classifiers: `python scripts/run_pipeline.py --scope sample --storage arrow-local`, then `--scope county`, `python scripts/verify_persistence.py --storage arrow-local`, and `python scripts/execute_notebooks.py --mode arrow-local --notebook task1_eda --notebook task2_preprocessing --report reports/windows_notebook_execution.json`. Use the existing `.venv/Scripts/python.exe` for these commands.

Do not execute the Task 3 notebook or training/final-evaluation scripts during this review. No WSL distribution or environment was removed.

# GridRescue notebook completion audit

Development run dated 21 November 2026. `PASS` means the cited output or test establishes the item, `PARTIAL` means usable evidence covers part of the requirement, `FAIL` means the check ran and failed, and `UNVERIFIED` means the check was deferred or evidence is unavailable.

The grading authorities are the [Task 1 PDF](../docs/requirements/Task%201%20for%20ML%20%281%29.pdf), [Task 2 PDF](../docs/requirements/Task%202%20for%20ML.pdf), [Task 3 PDF](../docs/requirements/Task%203%20for%20ML.pdf), [final ML PDF](../docs/requirements/ML_Project_Requirements_Final.pdf) and [Big Data DOCX](../docs/requirements/bigdata%20requirments.docx). The [bundle notes](../docs/requirements/README_START_HERE.md), existing design, research and defense documents provided context. Prior reports retain their original dates and scope.

## 1. Repository changes

- Updated the three canonical notebooks in place. Original notebook copies are in `artifacts/notebook_integration/originals/`. The executed notebooks retain original attachment bytes, section anchors and the navy/teal table formatter. Task 1 and Task 2 add executable checks and beginner explanations. Task 3 calls the existing source experiment and reads the same current artifacts as Task 2.
- Integrated the Task 3 development loader with the verified county storage backend, reconciled the development label data, and recorded its input paths and hashes. The source factory supplies the same model, features and time-aware score calculation for notebook and console runs. Added persisted prediction hashes, schema and split guards, and focused tests for Arrow-local provenance and frozen model reload.
- Added `gridrescue.inference` to freeze the selected specification, persist the whole fitted pipeline, and verify and score it outside Jupyter. Updated the README and design/defense guide and created the [beginner walkthrough](../docs/CODE_WALKTHROUGH.md).
- Git status was attempted before edits. The workspace has no `.git` directory and explicit `git --git-dir=.git --work-tree=. status --short` confirmed that no repository metadata was available. File and attachment comparisons against preserved originals provide the change evidence for the notebooks. `final_evaluation.py`, raw inputs, and the application source retained their original scope.

## 2. Data populations and executed Spark work

| Population | Raw or inventory records | Invalid records | Silver observations | Gold feature and label-audit anchors | Eligible train / validation |
|---|---:|---:|---:|---:|---:|
| Local EAGLE-I release years 2018–2022 | 122,019,012 data records plus five headers | — | — | — | — |
| Complete development source, 2018–2021 | 96,222,547 parsed by Spark | 6,618,821 with at least one integrity flag | — | — | — |
| Deterministic January prefixes, 2018–2021 | 400,000 | 66,369 | 333,631 | 333,631 each | 109,785 / 53,601 |
| Full-year fixed county cohort, 2018–2021 | 418,374 | 1,434 | 416,940 | 416,940 each | 303,791 / 102,449 |

The full development integrity audit reported 89,603,726 rows passing its record checks before deduplication. It scanned the four source CSVs one year at a time. Nationwide duplicate, gap, Silver, feature and label results remain **UNVERIFIED**. Both bounded scopes recorded zero exact duplicate removals and zero conflicting rows in these extracts. The Spark fixture exercises both rejection paths. The county cohort covers Los Angeles (`06037`), Miami-Dade (`12086`) and Harris (`48201`). It spans twelve months per year in the available reports. The two bounded extracts can overlap and were never concatenated. [Source inventory](source_manifest.json), [full development integrity audit](full_development_audit.json), [prefix audit](windows/sample/audit.json), [county audit](windows/county/audit.json).

Model training used the 303,791 eligible train anchors, including 110,987 positives (36.53%). The 102,449 2021 validation anchors included 33,719 positives (32.91%). The frozen refit uses all 406,240 eligible development anchors after selection. 2022 counts above are pre-existing file-inventory information. There was no 2022 data read, label generation, fit, tuning, prediction or evaluation during this run.

## 3. Task 1 checklist

| Requirement | Status | Evidence |
|---|---|---|
| Problem, user, binary target, measurable goals and limits | PASS | Scope and provenance cells describe the retrospective use and specify coverage, EDA and development evaluation goals. |
| Source, collection, attribution and reuse | PARTIAL | ORNL public utility outage map collection and the published CC BY 4.0 record are cited. The exact archive revision behind the local bytes remains unverified. [Figshare source](https://doi.org/10.6084/m9.figshare.24237376) |
| Read, random sample, shape, schema, original names/types, non-null counts and memory | PASS | Actual CSV ingestion, seeded ten-row inspection, counts and Spark type output. Reports Spark cache allocation and Python RSS separately from bounded pandas deep memory. |
| Descriptive statistics and column unique values | PASS | `describe()`, numeric Gold distributions, count-distinct results and state/county reporting frequencies. |
| Balance, missing values, duplicate checks and cleaning | PASS | Eligible class counts, source nulls, absent-slot diagnostics, exact key and quarantine checks, row reconciliation. |
| IQR flags, candidate treatments and decision | PASS | Prefix Q1 2, median 5, Q3 41, upper fence 99.5. The 51,859 flagged rows include plausible severe events. The notebook retains valid extremes and shows a log display. |
| Univariate and feature-versus-target | PASS | Distribution and box plots, category counts, UTC-hour coverage, and class-conditional means for all 13 inputs on eligible prefix rows. |
| Feature-to-feature, correlation and multivariate quality | PASS | Scatterplots, Pearson heatmap, VIF-style audit, exact `current − lag60` identity, observed history-size and rolling-variance checks. |
| GroupBy summaries, interpreted plots and three findings | PASS | State summaries, county/month coverage and severity, and dynamically generated findings with scope limits. |
| Rare categories and generalization | PASS | Reports sparse county-year coverage and discloses timing, conditional eligibility and geographic selection limits. |

Three executed examples are a prefix mean of 117.22 against a median of 5.00, 97.4% eligible anchors in the cleaned county cohort, and a peak observed county/month mean of 23,588.9 customers out in Harris in February 2021. The county/month mean counts repeated reports and does not identify unique customers or establish a cause. [Task 1 notebook](../notebooks/task1_eda.ipynb).

## 4. Task 2 checklist

| Requirement | Status | Evidence |
|---|---|---|
| Identify, create and review features | PASS | Explains the 13 positions, original/current and engineered fields, numeric UTC encodings, exclusions, missing flags and their redundancy. Task 2 checks sequence equality with Task 3's allowlist. |
| Exact lags, windowing and current/past-only X | PASS | Real Spark join verification and July manual trace. Tests cover gaps, future mutations and cross-county isolation. |
| X/y, three-hour outcome and complete future windows | PASS | Current count must be positive. Both classes require all twelve unique future slots. Missing histories are flagged before imputation. Missing outcomes are excluded. |
| Chronological split and leakage prevention | PASS | 2018–2020 train, 2021 validation, and a three-hour purge. 2022 remains sealed. The county keys are unique and class labels are binary. |
| Missing data, encoding and scaling | PASS | Spark train-only median imputer, vector assembly and standardization. Training-fitted statistics are applied to validation and interpreted using an actual missing-history example. Predictors are numeric, so categorical encoding is unnecessary. |
| Shape, actual examples, validation and storage | PASS | 163,386 prefix and 406,240 county eligible vectors. All targeted vectors have 13 entries and zero nonfinite values. Arrow-local fitted preprocessing reload and full vector parity are documented in the independent persistence report. |
| Task 3 and future inference compatibility | PASS | Task 3 consumes the same raw columns and learns its own preprocessing per fold. The saved sklearn pipeline owns deployment preprocessing. |

The exact-artifact round-trip evidence covers both bounded scopes with zero changed or extra rows. This run independently reloaded both saved Spark pipelines in a fresh process and found zero mismatches across all 569,626 fitted vectors. Arrow-local uses up to 500,000 rows, eight export partitions and Arrow batches of up to 8,192 rows. [Task 2 notebook](../notebooks/task2_preprocessing.ipynb), [Spark persistence proof](persistence_validation.json).

## 5. Task 3 checklist and measured model comparison

| Requirement | Status | Evidence |
|---|---|---|
| Research and justify three different classifiers | PASS | Notebook compares Logistic Regression, Decision Tree and Random Forest mechanics, use, parameters, limitations and primary references. |
| Consistent pipelines and genuine defaults first | PASS | All three defaults fit on 303,791 earlier anchors. The seeded trees and two-job forest keep the approved default learning settings. Complete parameters, timings, warnings and prediction files are in the development reports. |
| Chronological CV, fold-local preparation and uncertainty summary | PASS | New imputer, scaler and estimator per fold. Identical folds with explicit three-hour purges. Sample standard deviation describes variation across periods. |
| Bounded search and default-versus-tuned comparison | PASS | 13 configurations including defaults across three shared folds, for 39 fold fits. Logistic Regression kept its default. Tree and forest used their training-only CV winners. |
| Appropriate metrics and winner chosen from development | PASS | Selection used highest 2021 AP among three CV-selected configurations. Accuracy, precision, recall, F1, ROC-AUC, PR-AUC and confusion matrices use the same 2021 cohort. |
| Generalization and complexity | PASS | Full-training and 2021 AP gaps, fit runtimes and fitted model complexity appear in Task 3. |
| Error analysis, reliability, global/local XAI and ablation | PASS | 2021 false positives and false negatives, grouped error rates, reliability bins and Brier score, bounded permutation and local sensitivity, and current-count-only comparison. |
| Save/reload complete development pipeline | PASS | Refit of the frozen specification on 406,240 anchors and independent exact reload check on 100 anchors. |
| Once-only final 2022 evaluation | UNVERIFIED | Separately authorized stage. 2022 is sealed. |

### Same fold rows for all candidates

| Validation interval | Earlier train | Fold validation | Observed gap between last train and first validation anchor |
|---|---:|---:|---:|
| 2018 second half | 48,860 | 50,935 | 4 h |
| 2019 | 99,801 | 101,349 | 27 h |
| 2020 | 201,150 | 102,641 | 27 h |

The program checks the strict three-hour label horizon against declared fold boundaries. Observed cutoff gaps can be larger than three hours because the source has missing observations. [Full fold results, warning ledger and configuration](modeling/development.json).

### Default and CV-selected results on 2021

| Algorithm | Configuration | CV AP mean ± sample SD | Train AP | 2021 AP | PR-AUC | ROC-AUC | Accuracy | Precision | Recall | F1 | Fit seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Logistic Regression | Default, also CV choice | .4310 ± .0142 | .4332 | .3787 | .3787 | .5929 | .6613 | .3300 | .0284 | .0522 | .77 |
| Decision Tree | Default | .4001 ± .0078 | 1.0000 | .3592 | .5166 | .5568 | .5892 | .3942 | .4623 | .4255 | 3.02 |
| Decision Tree | Depth 12, minimum leaf 10, minimum split 2 | .4763 ± .0196 | .6147 | .4683 | .4622 | .6546 | .6759 | .5097 | .3976 | .4467 | 2.64 |
| Random Forest | Default | .5042 ± .0041 | 1.0000 | .4799 | .4818 | .6528 | .6725 | .5032 | .3827 | .4347 | 29.15 |
| **Random Forest** | **100 trees, depth 12, minimum leaf 10** | **.5403 ± .0139** | **.6131** | **.5237** | **.5237** | **.6832** | **.6942** | **.5553** | **.3556** | **.4336** | **43.00** |

The 2021 prevalence baseline is .3291 AP. The default tree and forest reached almost perfect training AP and fell substantially on 2021. The selected forest narrowed its AP gap from .5201 to .0895. Its 2021 recall fell from .3827 to .3556 at the fixed threshold, so the AP gain represents improved ranking rather than a better result on every threshold metric. Fit times are measured local durations and vary with CPU load. [Machine-readable comparison](modeling/comparison.csv), [Task 3 notebook](../notebooks/task3_modeling.ipynb).

At score `> 0.5`, the selected forest confusion matrix was `[[59128, 9602], [21728, 11991]]` in `[[TN, FP], [FN, TP]]` order. Los Angeles missed 72.5% of observed escalations versus 58.0% in Miami-Dade and 58.2% in Harris. Missing-history comparisons have only 361 validation anchors in the missing group. The current-count ablation measured .3746 AP versus .5237 with all features on the same rows, a gain of .1491. [County errors](modeling/error_by_fips_code.csv), [monthly errors](modeling/error_by_month.csv), [ablation](modeling/feature_ablation.csv).

The selected forest's 2021 Brier score was .2014, compared with .2221 for a constant score equal to 2018–2020 prevalence. The quantile-bin reliability diagram supports inspection of score behavior. Further validation would be needed to present calibrated probabilities. Shuffling `hour_utc` yielded the largest mean AP decrease (.1728 over three repeats on 1,500 validation anchors), ahead of current count (.0485). Reporting schedules and the label construction can contribute to those associations. For the Los Angeles anchor at 2021-01-01 00:00 UTC, replacing only `hour_utc` with its training median moved the score from .2749 to approximately .3725. This shows how the fitted pipeline responds to that input change while holding its other inputs fixed. [Diagnostics](modeling/development_diagnostics.json), [reliability bins](modeling/reliability_bins.csv), [permutation importance](modeling/permutation_importance.csv), [local sensitivity](modeling/local_score_sensitivity.csv).

### Frozen configuration and artifacts

The freeze uses seed 17, 100 trees, `max_depth=12`, `min_samples_leaf=10`, default Gini splitting and bootstrap sampling, and two local workers during fit. The complete fitted pipeline contains the ordered 13-feature median imputer, scaler and classifier. The frozen decision rule is score strictly above 0.5 for class 1. The pre-holdout refit took 50.57 seconds on the development cohort.

| Artifact | Path |
|---|---|
| Three default and the two changed CV-selected configurations, validation predictions | `artifacts/modeling/*_{default,cv_selected}.joblib` and `*_validation_predictions.parquet` |
| Model choice with development fingerprint | [Frozen selection](modeling/frozen_selection.json) |
| Fitted pre-holdout model and reload fixture | `artifacts/modeling/frozen_development_pipeline.joblib`, `artifacts/modeling/development_reload_sample.parquet` |
| Hashes, ordered features, target, version and threshold | [Frozen model metadata](modeling/frozen_pipeline.json) |
| Independent reload | [Exact development reload verification](modeling/development_reload.json) |
| Earlier Spark preparation | `artifacts/windows/{sample,county}/preparation/`, `artifacts/windows/{sample,county}/prepared_features/` |

## 6. Final ML project checklist

| Official section | Status | Evidence |
|---|---|---|
| 01 Problem and data understanding | PARTIAL | Target, intended use and scope documented. The workspace's exact archive revision is unverified. |
| 02 Cleaning and 03 EDA | PASS | Executed Task 1, population ledger and chart interpretations. |
| 04 Preprocessing and 05 build/train | PASS | Task 2 and Task 3 use the same feature/label contract, chronologically separated development and per-fold fitting. |
| 06 Evaluation, errors and reliability | PARTIAL | Development rankings, class metrics and diagnostics are in Task 3. Once-only held-out metrics are deferred by explicit instruction. |
| 07 Explainable AI | PASS | Seeded global permutation importance and a local real-anchor sensitivity analysis. Correlated features limit interpretation. |
| 08 Application/deployment | PARTIAL | Fitted pipeline, ordered inputs and fresh-process proof are ready. A user-facing prediction workflow, validation and errors, displayed XAI, score labeling, and a demonstrated launch/deployment remain separate work. |
| Submission package | PARTIAL | Source, notebook outputs, dependencies, provenance and current audit are available. Final test, application and short demo remain pending. |

## 7. Big Data checklist

| Official requirement | Status | Evidence |
|---|---|---|
| Team of 5–7 | UNVERIFIED | The team roster was unavailable in the supplied project material. |
| Data collection/source | PASS | Five locally inventoried files and attributed public source. |
| Data preprocessing | PASS | Spark CSV schema validation, parsing, quarantine, duplicate handling and measured Silver results for the two bounded scopes. |
| Meaningful Apache Spark processing | PASS | Full development integrity scan and scoped `DataFrame`, filter, groupBy/aggregate, exact-time joins, and time-range window operations. Parquet storage is bounded Windows Arrow-local. |
| EDA | PASS | Executed Task 1 charts and findings distinguish reporting coverage from severity. |
| Project-specific analytical method and evaluation | PASS | Three algorithms evaluated on the authorized county development cohort using common chronological folds and 2021 validation. |
| Interactive dashboard and project/model results | PARTIAL | Existing historical dashboard has prior KPI/filter/data reconciliation evidence. This run leaves final model-result/prediction integration and dashboard presentation for the application phase. [Prior verification](dashboard_verification.json) |
| Concise report, README and demo | PARTIAL | This audit and README document the method and evidence. Final course report and presentation/demo still need the held-out results and application. |

The prior bounded [performance comparison](performance_comparison.json) measured identical state aggregates with cached and uncached CSV queries. A fresh CSV-versus-Parquet benchmark is optional and was outside the evidence needed to establish the Spark rubric items.

## 8. Runtime, checks and visual integrity

| Check | Status | Result |
|---|---|---|
| Notebook structure and Python cells | PASS | `nbformat.validate`, `ast.parse` on every code cell, unique IDs, resolved notebook links and unchanged attachment bytes. |
| Installed dependencies, syntax and imports | PASS | `.venv` Python 3.12.14, PySpark 3.5.3, Java 17, sklearn 1.9.1, pandas 2.3.3, PyArrow 26.0.1. `pip check`, `compileall -q src scripts tests` and import checks passed. |
| Existing tests and new integration fixtures | PARTIAL | `python -m unittest discover -s tests -v` ran 46 tests with isolated local Spark storage. 45 passed. The failing test uses the native Hadoop writer. Both new tests passed. |
| Native Windows integration test | FAIL | `test_preparation_fits_only_training_and_saves_reload` fails while writing the native Spark pipeline. `HADOOP_HOME` and `hadoop.home.dir` are unset. Arrow-local notebook paths, format tests and reloaded preparation remain usable. An earlier rerun also hit ephemeral Spark shuffle-file errors that disappeared with isolated scratch storage. |
| Real Task 1 execution | PASS | 27 clean-kernel code cells. Real CSV, live cleaning, matching stored clean rows, Spark analysis and refreshed findings. |
| Real Task 2 execution | PASS | 19 clean-kernel code cells. Actual features, target safeguards, exact ordered transforms and stored preparation on both bounded scopes. |
| Real Task 3 execution | PASS | 22 clean-kernel code cells. Default, CV and tuning reports, diagnostics, freeze and new-process reload. No recorded estimator fit warnings. |
| Independent Spark preprocessing reload | PASS | `scripts/verify_persistence.py --storage arrow-local` compared 163,386 prefix and 406,240 county vectors. No dimension, finiteness, fitted-statistic or exact-vector mismatches. |
| Exact pre-holdout model reload | PASS | 100 of 100 labels and scores matched exactly, maximum score difference 0.0. The child process used only the local artifact and saved development fixture. |

Chrome local HTML render verification followed all 23 navigation links and loaded all 33 images. The 19 original attachment cells retain their exact content. Tasks 1 and 3 include 10 and 4 regenerated PNG plot outputs respectively. Task 2 retains its illustrated evidence as Markdown attachments. All 64 DataFrame tables rendered with the navy/teal formatter. The minimum observed table cell text contrast was 8.73:1 in this render. A screenshot review covered the covers, representative tables, and regenerated analytical plots. Browser checks used the files' actual Markdown and embedded outputs. Editor-specific rendering was outside this check. [Visual checks](../artifacts/notebook_integration/visual/browser_checks.json), [visual samples](../artifacts/notebook_integration/visual/visual_contact_sheet.png).

[Task 1 execution](../artifacts/notebook_integration/task1_execution.json), [Task 2 execution](../artifacts/notebook_integration/task2_execution.json), [Task 3 first execution](../artifacts/notebook_integration/task3_execution.json), [Task 3 final render execution](../artifacts/notebook_integration/task3_final_execution.json). The development workspace retains the isolated test log at `artifacts/notebook_integration/final_tests_isolated.log`.

## 9. Remaining scientific and submission work

- The conditional cohort excludes unobserved or incomplete outcomes. At inference time, future reporting completeness is unknown. Anchors often overlap and cannot be treated as independent outage incidents. Three preselected counties and numeric calendar encodings limit generalization, and distribution shifts can contribute to train/validation gaps. Score reliability remains development-only. Individual sensitivity to correlated inputs does not identify physical drivers.
- **2022 approval gate.** Review the frozen selection and fresh-process evidence. First verify the existing final path's native Spark Parquet writes in the intended runtime using development fixtures. Only after separate approval run the existing once-only evaluator and preserve its journal. The Windows native Hadoop failure could otherwise consume the gate on an interrupted evaluation. An interrupted journal requires explicit recovery approval.
- After the holdout, build the Streamlit prediction flow around validated current/past observations and the saved sklearn pipeline. Show understandable scores and XAI, integrate model evidence with the Big Data dashboard, verify KPIs/charts/filters, and finish the team roster, final course report and demo.

# GRIDRESCUE — THE COMPLETE PROJECT EXPLAINED
University ML + Big Data • Version 1.0 • November 16, 2026

---

## 01. The project in plain English
Our problem: Utilities and emergency planners care whether an electricity outage already observed in a U.S. county may worsen. GridRescue uses past records to estimate the risk of a substantial increase in affected customers within the next three hours.
Our deliverable: A reproducible PySpark pipeline, three ML assignment notebooks, a fair comparison of three classical algorithms for the same target, and a Streamlit dashboard backed by real aggregates and validated predictions.

### The input, target, and output
| Term | In GridRescue | Illustration |
|---|---|---|
| Input X | Current customers out, historical lags, past changes, rolling statistics, calendar features. | At 10:00 we know 500 customers out and the preceding hour. |
| Target y | Whether verified future observations show a material escalation during (t, t+3 hours]. | If an eligible future observation reaches the frozen threshold, y=1. |
| Predicted output | A probability between 0 and 1, then an alert class using a chosen threshold. | Predicted risk = 0.78; class = 1 if threshold is 0.50. |
| Actual outcome | The historical future event, used for training/evaluation only. | Later values tell us whether the prediction was correct. |
> **Careful wording.** The project predicts escalation conditional on an already-observed outage, not every new blackout, restoration time, physical grid failure, or live grid control.

### What is completed versus proposed?
The published dataset inventory is sourced, and the implementation design is ready. The actual local CSV row counts, cleaned data, label eligibility, trained model scores, and dashboard are not verified in this document. Codex must measure and record them. The university Task 1–2 discussion is permitted on November 17; Task 3 is due November 21.

## 02. Foundations: data, sequences and time
| Concept | What it means | How it relates to GridRescue |
|---|---|---|
| Dataset / row / column | Dataset = collection of records; row = one observation; column = one variable. | One row: county + timestamp + reported number of customers out. |
| Cross-sectional data | Different entities observed at roughly one time. | Compare counties at 10:00. |
| Time-series data | Repeated measurements indexed by time, where ordering and temporal gaps matter. | One county has outage measurements at multiple timestamps. |
| Sequential data | Any ordered observations (sentences, clicks, events); time intervals need not be regular. | Ordered outage events are sequential; timestamped county observations form a time series. |
| Panel / longitudinal data | Multiple entities each observed repeatedly over time. | Our whole dataset is county-level panel data with time-series structure. |
| Sampling frequency | How often a measurement is intended to occur. | EAGLE-I is nominally sampled every 15 minutes; gaps exist. |
| Forecast horizon | How far ahead we predict. | Future three-hour window after anchor time t. |
| Lag feature | Earlier value at a specific past time. | Customers out at exactly t minus 60 minutes, if observed. |
| Rolling window | Summary of a specified historical interval. | Mean or maximum reported customers out during [t-60 min, t]. |
| Trend / seasonality | Long-run change / repeating time-linked pattern. | Outage counts may vary by season; requires exploration. |
| Stationarity / autocorrelation | Stable time-series distribution / correlation with its own past. | Concepts to know; stationarity is not a requirement for tree-based classifiers. |

### Time-series analysis is not the same as forecasting
Analysis: Study historical temporal patterns. Forecasting: Predict a future value or event. Regression forecasting: Predict future number of customers out. Event classification: Predict whether severe escalation occurs. We do the latter with historical time-series features. The entire county-level collection is also a panel dataset.

## 03. The EAGLE-I data: provenance and risks
| Year | Published observations | Approx. CSV size |
|---|---|---|
| 2018 | 21,776,807 | 999.2 MB |
| 2019 | 24,074,123 | 1.10 GB |
| 2020 | 25,545,518 | 1.17 GB |
| 2021 | 24,826,103 | 1.14 GB |
| 2022 | 25,796,466 | 1.20 GB |
| 2018–2022 total | 122,019,017 | ~5.61 GB |
Source: Oak Ridge National Laboratory, EAGLE-I: Figshare dataset. Publication: Scientific Data (2024). Published counts are not proof of your downloaded local file counts.
| Source field | Meaning / correct treatment |
|---|---|
| fips_code | Five-character county ID; preserve leading zeros. Use for grouping/joining, not as a numeric magnitude. |
| county, state | Geographic labels; categories for EDA, not blindly numeric. |
| run_start_time | UTC observation timestamp; parse and sort reliably. |
| sum | Reported customers without electricity at that county/time. It is NOT energy consumed or kWh. |
> **The #1 dataset limitation.** The source omits zero-outage observations; an absent county-time record may mean no outage or a reporting gap. Do not automatically insert zeros. Missing values within rows and missing rows are different problems.
Large reported outage counts can be real disaster events; investigate rather than deleting all statistical outliers. Supplemental coverage and customer metadata may be useful context, but retrospective quality fields require careful consideration before being included as predictors.

## 04. TASK 1 — Understand, clean, and explore
Task 1 objective (from the course PDF): understand the data, prepare it for analysis, identify outliers, and perform EDA. The notebook must contain runnable code, output, short observations, cleaning justifications, and a concise summary.

### Part A: Data understanding — every required check
| Course requirement | What Codex must show in the notebook |
|---|---|
| Read data + random sample | Load CSV via Spark using explicit schema; show randomized representative records. |
| Shape / information | Rows, columns, types, non-null counts, and measurable/estimated memory or stored byte size. |
| Column names + description | Print actual source headers and explain each; descriptive statistics for counts/timestamps. |
| Unique values | Number of unique county IDs, states, dates and relevant columns; distinguish high-cardinality IDs. |
| Class balance (if classification) | Only after eligible labels are created: positive and negative counts and prevalence. State if not yet approved. |

### Part B: Cleaning and outlier handling
| Concept | How to handle it | Evidence to retain |
|---|---|---|
| Null values | Find nulls in existing rows; reject/repair only with justified rules. | Nulls per column before/after. |
| Missing timestamps | Analyze expected vs observed time slots; never silently fill absence as zero outage. | Gap report by county/year. |
| Duplicates | Check exact duplicate rows and conflicting county-time keys separately. | Examples, counts, chosen policy. |
| Invalid measurements | Investigate negative/nonintegral counts, unparsable UTC timestamps, malformed FIPS. | Quarantine with reason codes. |
| Outliers | Distinguish measurement errors from true severe outages; compare keeping vs transformation/capping. | Plots + decision rationale. |

### Part C: Five required EDA categories
| Required EDA | Practical GridRescue analysis |
|---|---|
| 1. Univariate | Distribution of reported outage counts, months, counties; summary statistics. |
| 2. Feature vs target | Compare current outages or historic growth with future-escalation label only if labels are defensible. |
| 3. Feature vs feature | Past 1-hour change vs rolling variation; current count vs fraction of estimated county customers. |
| 4. Correlation | Correlation of meaningful numeric features; not numeric correlation of county identifiers. |
| 5. GroupBy / statistical | Aggregations by state/year/month/hour; count, mean, max, coverage and interpretation. |
> **Defense question.** “What happened to your data?” Answer with measured raw rows → invalid/quarantined → valid observations → eligible labeled windows. Do not recite an invented percentage.

## 05. TASK 2 — Engineering a safe ML dataset
Task 2 objective: Identify features, create new ones, define X and y, split when appropriate, preprocess and save the prepared data. Stop before model selection or training.

### Feature engineering vocabulary
| Concept | What it is | In GridRescue |
|---|---|---|
| Feature extraction | Transform raw values into a usable representation. | Extract hour/day/month from UTC timestamp. |
| Feature generation | Build additional candidate features from known inputs. | Historical 60-minute change, rolling std, affected-customer ratio. |
| Feature selection | Choose predictors; remove identifiers, leakage and ineffective features. | Keep past-only features; judge optional features on development data. |
| Sequential feature selection | Add/remove predictors iteratively by validation performance. | Optional method; must use training-only time-aware folds. |
| Dimensionality reduction | Produce fewer derived dimensions, e.g., PCA. | Not currently required; can reduce interpretability. |

### Examples of features we intend to create
| Feature | Computation | Safety condition |
|---|---|---|
| customers_out_t | Current observed county count. | Use only actual observation at t. |
| lag_15m, lag_60m | Same county at exact earlier timestamps. | Missing exact lag must stay missing, not shift 4 observed rows. |
| delta_60m | count(t) minus count(t-60m). | Needs verified lag and no future data. |
| rolling_mean_60m | Average over prior 60-minute interval (including t). | Actual timestamp-based lookback; record completeness. |
| rolling_std_60m | Dispersion over past window. | Fit only on known historical values. |
| hour, weekday, month | Calendar components derived from UTC t. | Explicit timezone interpretation. |
| county_customer_ratio | count(t) divided by suitable county customer estimate. | Only if denominator validity and date applicability are established. |

### Prediction label: a proposal that must be audited
At time t, propose escalation if a verified future observation within (t, t+3h] reaches current count + max(200, 50% of current count). Example: current = 500, threshold = 750. A future verified 900 means positive under this definition. The 200/50% values are illustrative design parameters, not validated science. Fix any threshold using training-era evidence and do not inspect the final test to choose it.
> **Label feasibility gate.** For each anchor, report how many required future slots are observed, their maximum time gap, and whether a confident positive/negative can be assigned. An incomplete future window cannot automatically be negative. Record how selection affects the sample.

## 06. TASK 2 — Splits and preprocessing

### Which periods are for training, validation, and testing?
| Partition | Years | Purpose |
|---|---|---|
| TRAIN | 2018–2020 | Fit model parameters and learned preprocessing. |
| VALIDATION | 2021 | Compare models, tune settings and select alert threshold. |
| TEST — untouched | 2022 | Final honest estimate after development decisions are frozen. |
These are proposed year assignments, subject to eligible class counts and source quality. Never use a random row split of nearby observations from the same outage episode. Exclude anchors whose future three-hour outcome crosses a split boundary. For Task 3 use earlier-to-later folds within development periods.

### Preprocessing concepts the TA may ask about
| Term | How it works | Should GridRescue use it? |
|---|---|---|
| Imputation | Replace missing values using a train-fitted statistic or model. | For eligible predictor nulls only, with missingness flags where useful; do not invent missing source outage records. |
| Categorical encoding | Convert categories to numeric inputs, e.g. one-hot encoding. | If meaningful categorical predictors are used; guard high cardinality. |
| Standardization | z=(x−train mean)/train std. | Good for Logistic Regression; statistics fitted on train only. |
| Min-max scaling | (x−train min)/(train max−train min). | Optional; can exceed 0–1 for unseen values. |
| Normalization | Often scale feature vectors to unit norm (different from standardization). | Not generally needed for this task; discuss terminology precisely. |
| Tree scaling | Tree splits depend on ordering/thresholds. | Random Forest/boosting generally do not require feature standardization. |
| Class imbalance | Positive escalations may be rare. | Inspect prevalence; weight/tune thresholds where justified. |

### Seven leakage traps to be ready for
| Leakage type | Concrete wrong practice |
|---|---|
| Future-feature leakage | Using count(t+1h) or the next-three-hour maximum as an X feature. |
| Rolling-window leakage | Centered/forward rolling statistics that extend beyond time t. |
| Row-offset leakage | Using four previous observed rows as “60 minutes ago” despite gaps. |
| Split leakage | Same outage episode or overlapping target window crosses train/test periods. |
| Preprocessing leakage | Fit scaler/imputer/encoder to train + validation + test. |
| Feature-selection leakage | Use future test performance or y_test to decide features. |
| Retrospective availability | Use later-compiled coverage/weather/event fields as if known in real time. |
> **Correct sequence.** Define leakage-safe candidate features → assign eligible labels → chronological split → fit learned preprocessing on train → apply identical transformations to validation/test → save feature list, prepared splits, and fitted preparation artifacts.

## 07. TASK 3 — Research three algorithms
Task 3 objective: Build and fairly compare three different algorithms for the same target. Research, default pipelines, time-aware validation, hyperparameter tuning, diagnostics, comparison, final test and save/reload are all required.
| Algorithm | Mechanism | Why include / cautions |
|---|---|---|
| Logistic Regression | Linear score passed through sigmoid to estimate P(y=1). | Interpretable baseline; scaling often helpful; linear decision boundary. |
| Random Forest | Many decision trees trained on bootstrapped samples; aggregate votes/probabilities. | Nonlinear relationships; can be large/slow; trees less interpretable. |
| Histogram Gradient Boosting | Sequential trees correct residual loss/gradients using feature bins. | Often strong for tabular data; tune to avoid overfitting. |

### The professor-required experiment order
| Step | What you must actually do |
|---|---|
| 1. Research | Table: algorithm, rationale, strengths, limitations, key hyperparameters, links. |
| 2. Pipelines | Preprocessing + estimator combined, same feature definitions, fair comparison. |
| 3. Default baselines | Run each with default hyperparameters first; save runtime and metrics. |
| 4. Time-aware CV | Earlier→later folds; preprocessing fitted within each fold; report mean ± SD. |
| 5. Tuning | Use bounded GridSearchCV/RandomizedSearchCV or documented manual search; no final-test tuning. |
| 6. Diagnose | Compare train/validation metrics; inspect underfit/overfit and false positives/negatives. |
| 7. Choose winner | Select from development data, considering performance/stability/runtime. |
| 8. Final fit/test | Refit allowed training data and evaluate once on untouched 2022 test. |
| 9. Save + reload | Store entire pipeline, feature metadata, version, metrics; reload and predict in a new cell. |

### What is cross-validation (CV)?
A validation method that evaluates a model on several train/validation folds. For time-dependent data, folds must progress forward in time. Do not confuse cross-validation with computer vision (also abbreviated CV). Your TA said not to do deep learning/computer vision; the Task 3 rubric still asks for cross-validation or a defensible validation plan.

### Hyperparameter versus model parameter
A parameter is learned by fitting (e.g., Logistic Regression coefficients). A hyperparameter is a configuration chosen outside fitting (e.g., number of trees, max depth, regularization strength). Compare defaults first, then tune using development-only validation.

## 08. TASK 3 — Evaluation, errors, saved model
| Metric / concept | Meaning | Why it matters here |
|---|---|---|
| Confusion matrix | TP, FP, TN, FN counts. | Shows missed escalation events and false alarms. |
| Precision | TP / (TP + FP). | Of alerts raised, how many were real? |
| Recall | TP / (TP + FN). | Of actual escalation events, how many did we catch? |
| F1-score | Harmonic mean of precision and recall. | Balance alert quality and detection. |
| Accuracy | (TP + TN)/all. | Misleading alone if severe events are rare. |
| ROC-AUC | Ranking of positives vs negatives across thresholds. | Useful, but pair with PR-AUC for imbalance. |
| PR-AUC | Precision–recall performance across thresholds. | Sensitive to rare positive class; compare with prevalence. |
| Calibration | Does predicted 0.8 correspond to about 80% outcomes? | Important if dashboard displays risk probabilities. |
| Overfitting | Excellent train, weak future validation. | Guard with time-aware validation, simpler models and tuning. |
| Baseline | Majority class or simple persistence-derived rule. | Proves models improve over trivial prediction. |
For a regression fallback, the task would use three regressors and metrics such as MAE, RMSE and R² plus actual-vs-predicted/residual plots. That is an alternative only if the classification label fails and the team approves changing the objective.
> **What must be saved.** Full fitted preprocessing + chosen estimator, feature order, model version, environment/dependency versions, evaluation summary and a successful reload-and-predict check. The test set is inspected only after selection.

## 09. Big Data — What the coursework requires
The Big Data assignment requires data collection with provenance, data cleaning, meaningful Apache Spark/PySpark processing, EDA, project-specific analysis, an interactive dashboard, and final code/data/report/demo/README deliverables.

### The Bronze → Silver → Gold pipeline
| Stage | Input / action | Evidence |
|---|---|---|
| Raw / Bronze | Keep source CSV unchanged; inventory, schema, source timestamp, file hashes; optionally Parquet preservation. | Actual bytes, rows, types, provenance. |
| Silver | Typed valid observations, invalid quarantine, duplicate policy, UTC/FIPS consistency. | Row reconciliation, reasons, no invented zeros. |
| Gold | Time-indexed features and grouped summaries; separate analysis and ML tables. | Unique intended keys, temporal integrity, meaningful EDA. |
| ML-prepared | Eligible X/y windows, split tags, train-fitted transforms. | Feature list, exclusion audit, train/val/test counts. |
| Dashboard exports | Only compact aggregate and scored tables, not full raw CSV scans. | Fast filters and traceable KPI sources. |

### Core Spark concepts, with examples
| Concept | What it is / why it matters |
|---|---|
| Spark DataFrame | Distributed-style table abstraction; filter/select/groupBy joins/window calculations. |
| Transformation | Lazy operation (select, filter, withColumn, groupBy) forming a computation plan. |
| Action | Triggers computation (count, show, write, collect); avoid collecting huge datasets. |
| Partition / shuffle | Partitions split work; grouping/joining may redistribute records (shuffle) and cost time. |
| Window function | Compute history within each county ordered by actual timestamp. |
| Join | Combine data by key, e.g. county-year customer context; check row amplification. |
| Parquet vs CSV | Parquet is typed, compressed, column-oriented; benchmark same task on both formats. |
| Data skew | Some counties/years may dominate; Spark tasks can become imbalanced. |
| Local Spark vs cluster | Local mode demonstrates PySpark use; does not prove multi-machine deployment. |

### Dashboard requirements mapped to real outputs
| Requirement | GridRescue application |
|---|---|
| Title / explanation | Describe historical county outage risk and dataset limitations. |
| KPIs + charts | Reported customers out, valid observed periods, state/year trends, model scores only after validation. |
| Interactivity | Filters for state, county, date and severity; Plotly maps/charts when data permit. |
| Important findings | EDA interpretations, model comparison and observed vs predicted examples. |
| Presentation quality | Readable labels, units, limitations and evidence-backed numbers. |
Final Big Data deliverables: runnable source code or notebooks; source/working dataset link with attribution; working interactive dashboard; concise problem/data/methods/results/conclusion report; demonstration/presentation; setup and running instructions in README.

## 10. Codex: exact end-to-end execution order
| Phase | What Codex should build | Definition of done |
|---|---|---|
| 0. Preflight | Inspect downloaded files, environment, source headers, actual dates, source manifest; run Spark+Parquet smoke test. | RUN_STATUS records measured vs unverified facts. |
| 1. Ingest & clean | PySpark Raw/Bronze/Silver with tests and quarantine; run sample before full dataset. | Actual raw/retained/rejected counts reconcile. |
| 2. EDA | Task 1 notebook with every required subsection and written interpretations. | Notebook executes and plots cite actual data. |
| 3. Feature/target | Past-only Gold features; exact-time lags; three-hour eligibility audit with examples. | LABEL_FEASIBILITY either APPROVED or BLOCKED. |
| 4. Prepare | Chronological X/y/splits; train-only preprocessing; Task 2 notebook. | Saved prepared datasets and consistent columns; no model training yet. |
| 5. Compare models | Task 3 defaults, time-aware CV, tuning, metrics, winner, final test, save+reload. | Reproducible comparisons and real scores. |
| 6. Big Data & UI | Spark workloads and benchmark; compact exports; Streamlit dashboard. | Usable filters, all KPIs traceable to actual outputs. |
| 7. Audit & defense | Test scripts, Git hygiene, final report, source links, TA questions and QA. | Fresh run or documented limitations; no fabricated results. |

### Recommended repository
data/raw (unmodified downloaded CSVs) · scripts/ (reusable Spark pipeline) · notebooks/ (task1_eda, task2_preprocessing, task3_modeling) · src/ (shared functions) · tests/ · reports/ · artifacts/ · app/ (Streamlit) · README.md. Keep multi-GB data and secrets out of ordinary Git history.

### What to ask Codex to report back to you
- Actual input data: filenames, bytes, years, row counts, schema and data-quality issues.
- Task 1: before/after cleaning figures, EDA plots and one interpretation each.
- Task 2: added features, label-positive/negative counts, exclusions, splits, preprocessing and leakage tests.
- Task 3: baseline/tuned metrics, fold stability, runtime, chosen model, final held-out score and reload check.
- Big Data/UI: real Spark operations, CSV/Parquet timings, working app and its data sources.
- Blocked items: missing files, unproven labels, failed checks or unexecuted experiments.

## 11. Defense: comparisons to memorize
| Pair | Difference to explain |
|---|---|
| Time series vs sequential | Time series is timestamped; sequential data is ordered more generally. |
| Time-series analysis vs forecasting | Analysis describes historical behavior; forecasting predicts future outcomes. |
| Classification vs regression | A discrete class/probability vs a numerical continuous quantity. |
| Feature generation vs selection | Create candidates vs choose among candidates; extraction transforms source. |
| Sequential feature selection vs sequence model | Forward/backward variable selection vs model that explicitly processes ordered sequences. |
| Missing value vs missing row | Null within an existing record vs no observation for a time slot. |
| Outlier vs error | Rare large real event vs invalid measurement; not synonyms. |
| Normalization vs standardization | Unit norm or other normalizing conventions vs mean-zero/unit-variance z-score. |
| StandardScaler vs MinMaxScaler | Uses training mean/std vs training extrema/range. |
| Fit vs transform | Learn preprocessing parameters vs apply learned mapping. |
| Train vs validation vs test | Learn weights vs choose/tune vs one final unbiased measurement. |
| Random split vs temporal split | Shuffled row division vs strictly later holdout; temporal for forecasting. |
| Cross-validation vs computer vision | CV means validation folds or image-based field, depending on context. |
| Logistic vs linear regression | Class probability through sigmoid vs continuous prediction. |
| Random Forest vs boosting | Bagged trees trained largely in parallel vs sequential error correction. |
| Precision vs recall | How many alarms are correct vs how many real escalations are detected. |
| CSV vs Parquet | Row-oriented text vs compressed typed columnar format. |
| Spark transformation vs action | Lazy plan construction vs executed computation. |

## 12. Strict TA questions with usable answers
| Question | Answer structure |
|---|---|
| Why this dataset? | Public U.S. county-time outage observations, 122M published rows for 2018–22, meaningful temporal risk question, large enough for Spark; also acknowledge missing-zero ambiguity. |
| What is one row? | One reported county/timestamp count, not one outage event and not power usage. |
| Exactly what did you train? | A binary escalation-risk classifier, only if eligible labels were validated; name exact features from actual notebook. |
| What are your inputs/outputs? | X=past/current observed outage features; y=future 3h escalation label; model outputs probability and thresholded class. |
| What did you clean? | Read actual per-column/row evidence; name exact null/duplicate/invalid/quarantined counts, not generic claims. |
| How is lag_60m computed? | Match same county at exactly t−60m; an absent earlier record remains missing. |
| Why not random split? | It would place nearby parts of the same outage episode across train/test, making performance overoptimistic. |
| Why did you scale? | Logistic optimization benefits; fit on train only; tree models do not generally require it. |
| Where could leakage happen? | Using future count as input, forward rolling, retrospective metadata, or test-fitted preprocessing; show unit tests. |
| How know model is good? | Held-out future-period performance versus trivial baseline; precision, recall, PR-AUC, false-alert burden, calibration and limitations. |
| Why Spark? | Measured large-scale ingestion/cleaning, grouped and temporal computations, Parquet; benchmark actual operations. |
| Can you predict every blackout? | No: conditional escalation from observed outages; absent zero readings and reporting gaps constrain coverage. |

### Final discussion preparation checklist
- Open the real Task 1 notebook; explain one row, columns, original row count, invalid data, EDA findings.
- Open Task 2; point to the feature definitions, exact-time lags, eligibility rules, X/y and chronological split.
- Explain every preprocessing fit: where learned statistics came from and why test remained unseen.
- For Task 3, state three algorithms, defaults, CV, tuning, chosen metric, winner, final test, saved artifact.
- Be able to explain why the data source can not fully prove outage absence or physical cause.
- Have reports/WHAT_CHANGED_IN_DATA.md, reports/LABEL_FEASIBILITY.md, reports/RUN_STATUS.md open and accurate.

## 13. Rubric-to-output checklist and resources
| Course | Checklist for completion |
|---|---|
| ML Task 1 | Read, random sample, shape, info, names, describe, unique, class balance (if applicable), missing, duplicates, outlier detection/treatment; univariate, feature-target, feature-feature, correlation, groupBy; plots, notes, summary. |
| ML Task 2 | Identify candidate predictors/types/IDs/leakage; create/review features; define X/y; appropriate time split; fit preprocessing on train only; imputation, encoding, scaling if needed; processed shape/examples/checks; save artifacts; no training. |
| ML Task 3 | Three-algorithm research table; pipelines/default baselines; fair time-aware CV mean±std; tuning; model-specific metrics/plots; winner selected on validation; final untouched test; save/reload; runnable notebook. |
| Big Data | Collection + source; cleaning; real Spark/PySpark; EDA; project-specific analysis; interactive dashboard with title/KPIs/charts/filters/findings; code, dataset link, working app, concise report, demo, README. |

### Direct source links
EAGLE-I dataset: https://figshare.com/articles/dataset/24237376
Scientific dataset publication: https://doi.org/10.1038/s41597-024-03095-5
Course source documents: Task 1 for ML (1).pdf, Task 2 for ML.pdf, Task 3 for ML.pdf, and the user-supplied Big Data requirements screenshot.
> **Honesty rule.** This explains the designed project and exact assignment expectations. None of the planned data cleaning results, model metrics or dashboard features should be claimed complete until Codex has run and verified them.
Recommended study order before discussion: 1 → 2 → 3 → 4 → 5 → 6 → 11 → 12. Read Tasks 3 and Big Data sections once your immediate Task 1–2 defense is secure.

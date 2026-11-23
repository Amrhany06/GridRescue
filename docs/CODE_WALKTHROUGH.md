# GridRescue code walkthrough

Follow the notebooks in order. Task 1 examines the data, Task 2 creates the features and labels, and Task 3 trains and compares the classifiers. The [completion audit](../reports/NOTEBOOK_COMPLETION_AUDIT.md) records which checks ran and what they showed.

## 1. Read and clean source reports with Spark

In `gridrescue.pipeline.read_source`, `csv.reader(stream)` reads the first record from each selected file. `next(...)` returns that record, which must match `SOURCE`. `spark.read.schema(...).csv(...)` then loads those files into a Spark DataFrame. The five original columns are strings at this stage. That preserves the leading zero in a FIPS such as `06037` and the original token when an outage count fails validation.

In `clean(raw)`, `F.col('fips_code')` creates a Spark expression referring to a named column. It does not bring its values into Python. `withColumn()` returns a DataFrame with an added or replaced column and leaves its input unchanged. `try_to_timestamp` and `try_cast` return null when a token cannot be parsed. Validation also checks geography, nonnegative integer counts, and quarter-hour alignment. Spark combines the failed checks into `reason`. `filter("reason != ''")` keeps the rejected rows and their reasons.

`dropDuplicates(SOURCE)` removes repeats across all five source fields. `groupBy(*KEY).count()` expands the two names in `KEY` and counts the distinct records sharing each county and timestamp. If a key still occurs more than once, an inner `join()` retrieves every conflicting row for quarantine. A left anti join keeps the valid rows that have no matching conflict key. The function returns `(silver, rejected, stats)`. Commas on the assignment side unpack that tuple into three names. The row ledger checks that invalid rows, exact duplicate removals, conflict variants and Silver sum to the raw count.

**TA question** What would change if we deduplicated on just FIPS and timestamp? Spark could keep one conflicting record arbitrarily. That count could change features and labels at nearby anchors.

## 2. Summarize and interpret observed data

In Task 1, `orderBy(F.rand(seed=17)).limit(10)` assigns seeded random sort values, sorts the available prefix rows, and limits the display. That sample describes the deterministic January prefixes. Spark uses its execution engine for `count()`, `first()`, and `toPandas()`, which are actions that request results. The notebooks use bounded transfers for plotting. A call to `.cache()` asks Spark to reuse evaluated data across actions.

`groupBy('state').agg(...)` calculates one output row per observed state. `F.avg('customers_out')` gives the mean over reports in each group. `.alias(...)` gives the result a readable name. The county/month plot divides summed counts by the number of observations, so a day with fewer observations contributes fewer values to the monthly mean. A report count is a count of timestamped rows. One event can contribute many rows.

`silver.approxQuantile(...)` estimates Q1, median and Q3. IQR is `Q3 - Q1`. Task 1 counts values above `Q3 + 1.5 * IQR` and shows alternative treatments on a bounded sample. The pipeline retains plausible extremes. `.corr()` measures linear association among available feature pairs in the plotting data. For the VIF-style check, regress one predictor on the others and use `1 / (1 - R²)`. Exact dependence makes that quantity effectively infinite. In the complete-lag sample, `delta_60m = customers_out_t - lag_60m` gives an exact dependence among three predictors.

**TA question** Why compare prefix EDA to a separate county summary? The prefixes come from January and support the worked Spark examples. The fixed counties cover all months and support the model experiment. Their extracts overlap in some source rows, so concatenating them would duplicate anchors.

## 3. Build exact historical features and labels

In `gridrescue.pipeline.features`, `F.unix_timestamp('timestamp')` converts a moment to epoch seconds. `Window.partitionBy('fips_code')` isolates each county, `orderBy('epoch')` sets the order, and `rangeBetween(-3600, 0)` chooses every observed record from one hour before the anchor through the anchor itself. `F.avg(...).over(w)` evaluates the mean over that window for each row. The function returns the original anchors with additional columns for past-hour mean, population variance, and history coverage.

The exact lag uses a left join on county and epoch. For the 15-minute lag, the lookup adds `900` seconds to each historical epoch. A 09:45 record then joins to the 10:00 anchor in the same county. If 09:45 is absent, the anchor remains and `lag_15m` is null. The one-hour lookup uses 3,600 seconds. Task 2 shows the explicit join and a manual check for a real county anchor.

In `audit_labels(gold)`, the forward window `rangeBetween(900, 10800)` starts at the first future slot and ends three hours later. Clean county-time keys are unique and grid-aligned. Therefore a count of twelve certifies the twelve required slots. For positive current counts, we compare the future maximum to `current + max(200, current * 0.5)`. Spark `F.when(condition, value)` produces null without an `otherwise` when the condition fails. An incomplete outcome stays null, even if the observed portion includes a large increase. Future columns are audit fields and supervise y only.

**TA question** Why is `lag(4)` unsuitable for the one-hour feature? It moves back four available records. If any record is missing, the result can come from earlier than one hour before the anchor.

## 4. Split, impute and scale

The three partitions are 2018–2020 training, 2021 development validation and sealed 2022 final testing. The split expression purges anchors whose label horizon reaches the next partition. An anchor at 21:00 on December 31, 2020 reaches midnight on January 1 after three hours, so it is purged. At 20:45 its horizon ends at 23:45 and stays eligible if all other rules are met.

Task 2 defines X in this precise order. Geography, raw timestamps and outcomes remain available for grouping and auditing.

| Position | Predictor | Purpose |
|---:|---|---|
| 1 | `customers_out_t` | Current reported severity |
| 2 | `lag_15m` | Exact recent severity |
| 3 | `lag_60m` | Exact one-hour reference |
| 4 | `delta_60m` | Current count minus the one-hour reference |
| 5 | `rolling_mean_60m` | Typical severity in the observed past hour |
| 6 | `rolling_variance_60m` | Variability in the observed past hour |
| 7 | `history_slots_60m` | Historical coverage from one to five slots |
| 8 | `hour_utc` | Time of day |
| 9 | `weekday_utc` | Day-of-week code, with Spark Sunday equal to 1 |
| 10 | `month_utc` | Seasonality baseline |
| 11 | `lag_15m_missing` | Flags an absent exact 15-minute observation |
| 12 | `lag_60m_missing` | Flags an absent exact 60-minute observation |
| 13 | `delta_60m_missing` | Flags missing one-hour change and duplicates position 12 under this contract |

`prepared.filter("split = 'train'")` selects only the earlier eligible rows for fitting. The Spark `Imputer` learns a median per column. Medians are less affected by extreme counts than means. The imputer fills missing input cells and the flags preserve which observations were missing. `VectorAssembler` packs the imputed values into a vector in the supplied order. `StandardScaler` centers each feature and divides by its fitted spread. This helps regularized Logistic Regression when raw counts and calendar codes have very different scales. Spark uses sample standard deviations and its imputer can approximate medians. The sklearn implementation uses population standard deviations and its own fitted medians.

`fit()` learns a stage's statistics from the supplied training rows. `transform()` applies those learned settings to new rows. The same fitted Spark preparation transforms both development partitions. Task 2 checks every county vector for thirteen finite values. All inputs are numeric and require no categorical encoder. Feature engineering creates inputs, such as the past-hour variance. Feature selection chooses which inputs to keep. The known redundant flags remain in the fixed contract.

**TA question** Why not pass the saved Spark vectors directly to Task 3 CV? The 2018–2020 fit learned statistics from periods that some CV folds treat as validation. Each fold has to start with the raw ordered features and fit preprocessing on its earlier rows.

## 5. Train and compare three classifiers

`gridrescue.modeling.make_model(name, parameters)` returns a scikit-learn `Pipeline`. A `ColumnTransformer` selects the allowed feature names and a nested pipeline runs `SimpleImputer` then `StandardScaler`. The outer pipeline fits the estimator on those transformed values. `frame[FEATURE_COLUMNS]` selects columns by name in the given order and `frame.candidate_y` supplies labels. `model.named_steps['classifier']` retrieves the fitted estimator by the name used in the pipeline.

| Classifier | How `fit()` learns | Key hyperparameters and prediction |
|---|---|---|
| Logistic Regression | Optimizes regularized logistic loss to learn weights and an intercept | Smaller `C` strengthens regularization. The sigmoid maps a weighted sum to a class-1 score. `max_iter` bounds solver iterations. |
| Decision Tree | Chooses splits that reduce class impurity, then repeats within branches | `max_depth` limits levels. `min_samples_split` controls whether a node can split and `min_samples_leaf` limits how small each child can be. The final leaf's class fraction is its score. |
| Random Forest | Fits many trees on bootstrap samples with random candidate predictors at splits | `n_estimators` controls tree count. `max_depth` and `min_samples_leaf` constrain individual trees. The forest averages the trees' class scores. |

Task 3 records all three defaults before testing alternatives. `chronological_folds()` constructs a Boolean time mask, and `np.flatnonzero()` returns its matching row positions. `.iloc[...]` uses those positions to slice a DataFrame. Initial training uses the first half of 2018 and validates in the second half. The next two folds validate on 2019 and 2020, with earlier years added to training. Each fold enforces the same horizon purge and has both classes.

`gridrescue.experiment.cross_validate()` builds a fresh pipeline in its loop and returns metrics per fold plus their means and sample standard deviations. Its role parallels sklearn's CV utility, while the project loop also records per-fold time, cutoff evidence, and warnings. `SEARCH` contains two Logistic Regression `C` alternatives and four configurations for each tree algorithm. The default also competes. Mean training-fold validation AP selects a configuration per algorithm. Of those three configurations, the highest 2021 AP wins. The recorded model order breaks an exact overall tie.

**TA question** Why use later years for validation and 2021 for selection? Random splitting can put neighboring anchors with heavily overlapping outcomes on both sides. Forward folds approximate predicting later observations with earlier training. The extra development year gives all candidate algorithms the same later comparison cohort.

## 6. Interpret metrics and explanations

`predict_proba(X)` returns a two-column array for these classifiers. `classes_` identifies which column corresponds to class 1. `predict(X)` returns a class. The project uses score `> 0.5` for class 1, with exact ties assigned class 0. Precision is the observed escalation share of predicted positives, recall is the caught share of observed escalations, and F1 combines them. Accuracy counts correct labels across both classes. The confusion matrix uses actual classes as rows and predictions as columns.

Average precision summarizes precision as recall rises through the ranked scores. It emphasizes the positive class and does not lock model choice to one threshold. The notebook reports trapezoidal PR-AUC separately, using a different calculation on the precision–recall curve. ROC-AUC summarizes how well the score ranks positives above negatives. For a single-class cohort the project leaves ranking metrics undefined.

The notebook groups actual errors by county, month and missing history. False-negative rate divides by observed positives and false-positive rate divides by observed negatives. The reliability plot compares mean model score with the observed escalation fraction in quantile bins. Brier score averages squared error between the score and observed zero or one. It measures probability error and is sensitive to both discrimination and reliability.

Global permutation importance shuffles one feature at a time on a fixed 2021 sample and measures the AP drop. Local sensitivity replaces one feature of an actual anchor with its training median and measures the score change. A change to one of the linked lag and delta inputs can create a combination that could never occur naturally. Read the chart as model sensitivity. The current-count-only ablation fits the same selected estimator configuration on the same earlier rows with one original predictor and compares it on the same 2021 rows.

**TA question** Can individual permutation importance establish physical causes or fully account for correlated features? Correlated inputs can stand in for each other, and the shuffle creates unusual combinations. The measured change describes this model under the chosen perturbation.

## 7. Save and verify reproducible inference

The Spark preparation artifact stores the fitted stages' statistics and order. `load_preparation(path)` reconstructs the fitted stages and Task 2 applies them without refitting. On Windows, Spark computes the rows and the bounded Arrow-local adapter encodes them as Parquet for storage. Each part is checked against its stored hash.

After 2021 selection, `gridrescue.inference.freeze_pipeline()` fits the chosen sklearn pipeline on all eligible development anchors. It saves the fitted imputer, scaler, and classifier together. The metadata records the target, ordered features, versions, settings, threshold, and SHA-256 artifact hash. `verify_development_reload()` starts a separate Python interpreter. That process checks the artifact and sample hashes and compares every score and class in the frozen fixture with the original predictions.

Use `load_frozen_pipeline()` and `predict_escalation()` to score a pandas DataFrame with the exact Task 2 features. A future Streamlit interface must construct those features from correctly validated history. The 2022 data remains sealed under the existing once-only evaluation procedure.

**TA question** Why hash an artifact before loading it? The hash checks that the bytes match the locally generated model referenced in the metadata. A joblib artifact is trusted only when it comes from the project-controlled source.

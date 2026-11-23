# Approved experiment: implementation decisions

This extends the existing Spark data pipeline and does not alter the approved target, source policies, or three-county population. Approval is recorded in `reports/target_approval.json`.

## Boundaries and data flow

- Existing Spark functions own source validation, cleaning, exact-time features and provisional label computation.
- Task 2 persists raw-feature Gold/label-audit and train-fitted Spark preparation. The current Windows execution uses the verified, bounded Arrow-local backend. Task 3 resolves the county paths from the persistence report and verifies the Parquet manifest before loading the cohort.
- Task 3 loads only eligible raw-feature county development anchors from 2018–2021. The 13-feature allowlist excludes identity, future diagnostics and y. Do not use globally imputed/scaled vectors in CV.
- Scikit-learn Pipelines refit numeric median imputation and standardization inside every training fold. Logistic Regression, Decision Tree and Random Forest share the same feature definitions and cohort. The sklearn scaler uses population standard deviation, while the standalone Spark Task 2 scaler uses sample standard deviation; these are separately fitted preparation implementations and must be described accurately.

## Evaluation and tuning

Models are Logistic Regression, Decision Tree and Random Forest, per the user's subsequent explicit algorithm change. No Histogram Gradient Boosting experiment was run. Seed 17; bound CPU threads for repeatability and responsiveness. Fit all three full-training default baselines first, changing only the seed and RF's execution parallelism, then perform common CV. Use three expanding folds within 2018–2020: first-half 2018 → second-half 2018; all 2018 → 2019; all 2018–2019 → 2020. Training label endpoints must be strictly earlier than validation start; validation label endpoints must remain inside the evaluation interval. Every fold must contain both classes and a chronological embargo of at least three hours. 2021 is held out from CV/tuning and used for development comparison/winner selection.

Primary metric: average precision. Also report trapezoidal PR-AUC distinctly, ROC-AUC, precision, recall, F1, accuracy, confusion matrices, prevalence and fit time. Use the frozen 0.5 decision threshold; do not tune it on 2022. Report fold mean ± sample standard deviation. Overlapping anchors are dependent; these fold variations are not independent-event confidence intervals.

Fit default baselines for all three before searching. Search two Logistic Regression C values and four controlled configurations for each tree model, retaining the default when it wins CV. Decision Tree varies max_depth, min_samples_split and min_samples_leaf; Random Forest varies n_estimators, max_depth and min_samples_leaf. The tree candidates include controlled one-parameter contrasts rather than an unbounded grid. Compare each default against its CV-selected configuration on 2021. Choose the winner by development average precision, with a deterministic tie rule. No 2022 access during these stages.

## Final evaluation and reload

The development notebook records the frozen selection, refits on 2018–2021 and verifies the saved full pipeline on a development fixture. A separately authorized final run uses the existing evaluation entry point and the same fixed counties. Its persistent once-only journal is written before test access. That entry point replays a completed result and requires explicit recovery approval after an interrupted or failed evaluation. Verify native Spark output in the intended runtime before opening the holdout.

Fresh-process inference must load that artifact and reproduce stored sample probabilities/predictions. Engineered inputs require past-only Spark features and up to one hour of observed history; a single raw current record does not contain that history. No new raw-input or national deployment capability is implied.

The [completion audit](../reports/NOTEBOOK_COMPLETION_AUDIT.md) records the measured development results and the status of the holdout.

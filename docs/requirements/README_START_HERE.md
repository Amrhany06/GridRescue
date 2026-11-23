# GridRescue — Three revised ML notebooks (21 November 2026)

**These are actual `.ipynb` files, intended to replace the corresponding files under the real `GridRescue/notebooks/` directory only after backing up the current originals.** They are *not* self-contained datasets or a rewritten repository. Reuse the real `src/gridrescue/` code, artifacts, reports and five source CSVs in the user's active checkout.

## What is included

| File | Coverage newly emphasized | Status |
|---|---|---|
| `task1_eda.ipynb` | Explicit problem, target, users, measurable success, EAGLE-I source/license verification note, source-versus-model cohort ledger, raw schemas and sampling, descriptive charts, multicollinearity/VIF, rare geography/coverage considerations, **three dynamically computed evidence-backed findings** | Original November 17 measured outputs retained in unchanged cells; **new cells must run locally** |
| `task2_preprocessing.ipynb` | Complete 13-feature ordered schema, accepted/rejected candidate features, exact-time lag checks, missing-history and outcome policy, split/purge/leakage, training-only Spark preprocessing, full-year county cohort prep, duplicate indicator audit, saved-pipeline explanation | Original measured output retained; **new county-specific cells must run locally** |
| `task3_modeling.ipynb` | Research of LR/tree/forest, actual sklearn pipeline code, defaults before tuning, time-purged expanding CV, mean ± SD, bounded grids, comparison, class imbalance, 2021 winner, confusion matrices, error/reliability, global/local model sensitivity, engineered-feature ablation, frozen final 2018–2021 fit, fresh-process model reload and **explicitly gated once-only 2022 test** | **Not executed on the actual GridRescue dataset here.** Synthetic-only functional smoke test passed for modeling and reload, not a grade or real result |

## Important: what is and is not complete

**Implemented in notebook source:** Tasks 1–3's rubric sections and accompanying end-to-end experimental method. The first two original notebooks contain saved previous source-derived outputs; newly inserted cells contain no fabricated output. Task 3 contains no fabricated real-data metrics. The real full 2022 test is disabled by default and needs deliberate approval.

**Still to verify / complete in the active repository:**

1. Confirm the latest source modules exist, especially `gridrescue.pipeline`, `gridrescue.storage` and `gridrescue.dashboard_data` used by Tasks 1/2. The available older `check ml.zip` snapshot is **not** the up-to-date codebase and lacks `storage.py`; do not assume that archive is runnable with these notebooks.
2. Run all notebook cells in clean kernels with the locally available **2018–2021** input artifacts. Record new numerical output, test code/source compatibility, inspect warning messages and compare row counts to saved audit evidence. No real-data runs were possible in this artifact-creation environment (raw CSVs and latest repository modules were not supplied).
3. Run Task 3 real three-model baselines, CV, tuning, comparison, explainability and full-year training. Inspect warnings and resource use. Save and independently reload the selected model. Check the target-approval record and feature contract before training.
4. After selecting and freezing the winner, deliberately authorize the **single** 2022 evaluation. **Do not use 2022 for model choice or hyperparameter tuning.** Treat an interrupted final evaluation as a scientific review event rather than silently retrying.
5. For **Big Data** compliance, verify actual Spark data ingestion, transformation, filters/grouping/windowing and source-scale evidence. The earlier full 2018–2021 audit was integrity-only, **not** full-country Silver/Gold processing. Do not claim otherwise.
6. **The two-course final project is not complete from notebooks alone.** Big Data requires a functioning interactive dashboard, a concise report, attribution, README and demo. ML requires a working application with real inference, input validation, explanation and launch guidance. Build the **working Streamlit app first** after Task 3; consider React only if time allows. Verify the team has 5–7 members under the Big Data rubric.
7. Verify the **exact downloaded Figshare archive version and its declared reuse license**; recent versions are reported as CC BY 4.0, but the file version in this workspace was not determined.

## Scientific contract (do not change silently)

- **Prediction:** whether a **current positive reported** county outage count grows by at least `max(200, 50% of current)` in the following 3h.
- **Label:** 12 expected *exact* 15-minute future records must exist; otherwise `candidate_y` remains null. Incomplete windows are **not** negative examples.
- **X:** exact ordered 13 numeric predictors from Task 2. `fips_code`, `county`, `state`, `timestamp`, and all future audit fields are excluded from X.
- **Partitions:** CV within 2018–2020, 2021 for model selection, protected 2022 for once-only test. Training and fold preprocessing are fit only on earlier rows.
- **Primary population:** the preselected Los Angeles (06037), Miami-Dade (12086) and Harris (48201) counties across 2018–2021; not nationwide representative.
- **Reporting:** historical conditional classifier; scores are not calibrated outage probabilities or operational alerts by default.

## Safe execution / placement

1. Back up the current canonical `notebooks/task1_eda.ipynb`, `task2_preprocessing.ipynb` and `task3_modeling.ipynb` files.
2. Copy these three files into `notebooks/` in your working GridRescue checkout. Don't replace any `src/` code blindly.
3. Start VS Code with the correct existing `.venv` interpreter and open the project root. On Windows, use the project's verified Arrow-local storage configuration if native Spark Parquet remains unavailable.
4. Run Task 1, then Task 2. Fix data/contract issues **before** Task 3; the chronological-label/feature schema should be frozen. Run development-only Task 3 cells, verify real results, then separately authorize its final test after reviewing the frozen choice.
5. Give Codex this bundle plus the active repository for a **read-only integration audit**. Its key job is to identify any mismatches with the latest `src/` APIs and local persisted artifacts, not regenerate the notebooks unnecessarily.

## Validation actually performed here

- `nbformat.validate()` passed for all three notebooks.
- Every Python code cell passed `ast.parse()` syntax validation.
- An independent synthetic-only sklearn run exercised default three-model training, three chronological CV folds, hyperparameter tuning, 2021 selection, metrics, reliability plots, global/local explanations, feature ablation, frozen-model persistence and **fresh-process reload**. The final 2022 test remained sealed. Synthetic scores are **not embedded in submitted notebooks**.
- **Not performed here:** executing Task 1/2 with actual Spark inputs, validating latest real repository dependencies, training real Task 3 classifiers, once-only 2022 evaluation or delivering the final application.

## Original dataset sources

- EAGLE-I / ORNL archive: https://doi.org/10.6084/m9.figshare.24237376
- Scientific Data methods paper: https://doi.org/10.1038/s41597-024-03095-5
- scikit-learn documentation: https://scikit-learn.org/stable/supervised_learning.html

This package is designed for **honest, reproducible code-level discussion**, not for pretending unexecuted requirements have been empirically satisfied.

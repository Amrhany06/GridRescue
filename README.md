# GridRescue

GridRescue is a university machine learning and Big Data project that estimates whether an **already reported county electricity outage** will escalate within the next three hours. The original Task 3 compared **Logistic Regression, Decision Tree, and Random Forest** and selected **Random Forest**. We later added **XGBoost** to the same project as part of a broader geographic and historical-feature study. XGBoost is the current experimental champion on that expanded benchmark. Final model selection across the two stages remains open.

Start with the [TA progress summary](docs/TA_PROGRESS_SUMMARY.md) for the full three-model comparison, the research progression, and the remaining work.

## Data and notebooks

Oak Ridge National Laboratory's EAGLE-I dataset records reported customers without power at 15-minute intervals. GridRescue uses **2018–2020 for training and chronological cross-validation** and **2021 for development evaluation**. The **2022 final holdout remains sealed**. A positive label requires the reported count to increase by at least the larger of 200 customers or 50% of the current count in any of the next 12 quarter-hour slots. Both classes require all 12 exact slots, so incomplete future coverage leaves the outcome unknown. [EAGLE-I archive](https://figshare.com/articles/dataset/24237376) · [Dataset paper](https://doi.org/10.1038/s41597-024-03095-5)

| Course task | Executed evidence |
| --- | --- |
| **1. Cleaning and EDA** | Schema, missingness, duplicates, valid extremes, class balance, reporting coverage and exploratory charts. [Task 1 notebook](notebooks/task1_eda.ipynb) |
| **2. Feature engineering and preprocessing** | 13 ordered numeric predictors, exact time lags, past-only windows, missingness flags, chronological splits and train-only Spark preprocessing. [Task 2 notebook](notebooks/task2_preprocessing.ipynb) |
| **3. Modeling** | Algorithm research, default baselines, fold-local preprocessing, chronological CV, tuning, comparison, diagnostics and saved-pipeline reload. [Task 3 notebook](notebooks/task3_modeling.ipynb) |

The notebooks retain their saved tables and figures. The [notebook completion audit](reports/NOTEBOOK_COMPLETION_AUDIT.md) maps the outputs to the course requirements.

## Original Task 3 results

The models trained on 303,791 eligible reports from Los Angeles, Miami-Dade and Harris counties and were compared on the same 102,449 eligible 2021 reports. Average precision (AP) measures how well the scores rank positive cases across thresholds. The 2021 positive rate was 32.91%. Precision and recall below use a score strictly above 0.5.

| Classifier | Configuration selected by training CV | 2021 AP | Precision | Recall |
| --- | --- | ---: | ---: | ---: |
| Logistic Regression | Default (`C=1`) | 0.378743 | 33.00% | 2.84% |
| Decision Tree | Depth 12, minimum leaf 10, minimum split 2 | 0.468337 | 50.97% | 39.76% |
| **Random Forest** | **100 trees, depth 12, minimum leaf 10** | **0.523669** | **55.53%** | **35.56%** |

Task 3 selected Random Forest because it had the highest 2021 AP among the three configurations chosen by chronological CV. Its tuning improved AP from 0.479885 and reduced the train-to-development AP gap. Its recall at the fixed cutoff fell from 38.27% to 35.56%. The selected pipeline was refit on all 406,240 eligible development reports and saved with its fitted imputer, scaler and classifier. A fresh process reproduced all 100 fixture scores and decisions exactly. [Complete comparison](reports/modeling/comparison.csv) · [Frozen selection](reports/modeling/frozen_selection.json) · [Pipeline metadata](reports/modeling/frozen_pipeline.json) · [Reload evidence](reports/modeling/development_reload.json)

## XGBoost extension and geographic testing

The extension evaluated state and county FIPS encoding, expanded to 20 counties, and added up to three hours of past-history features. It compared Random Forest and CPU XGBoost variants on matched development rows. The experimental champion uses extended history, UTC hour and state, with 120 boosting rounds and depth 6. It trained on **1,053,328** eligible reports from 12 counties in 2018–2020 and scored **582,532** eligible 2021 reports from 20 counties, including four unseen counties in represented states and four in unseen New York.

On those rows XGBoost reached **AP 0.411168, precision 34.00%, recall 56.45%, and accuracy 68.89%**. Its cutoff came from 890,035 chronological out-of-fold (OOF) scores, using the highest-accuracy cutoff that attained at least 60% recall on those earlier scores. The original Task 3 table uses a different cohort, feature set and decision rule. [Expanded comparison](reports/modeling/local_improvement/MODEL_COMPARISON.md) · [Geographic holdouts](reports/modeling/county_expansion/GENERALIZATION_REPORT.md) · [Precision–recall figure](reports/modeling/precision_diagnostic/results/precision_recall.png)

The independent audit checked data lineage, temporal leakage, model integrity and geographic transfer. A no-fit replay reproduced the archived XGBoost metrics and cutoff. At a descriptive 60% recall, precision was 37.87% in seen counties, 29.65% in unseen counties in represented states, and 12.24% in unseen New York. Results apply to historically observed reports with complete subsequent coverage. Transfer to other states, calibrated risk and incident-level alert performance remain unverified. [Scientific audit](reports/modeling/independent_audit/MASTER_REMEDIATION_PLAN.md) · [Replay output](artifacts/post_audit_evaluation.json)

## PySpark and the dashboard

PySpark handled CSV ingestion, type and quality checks, quarantine, grouping, exact-time joins and window functions. The full development integrity scan parsed **96,222,547** records. The complete Bronze → Silver → Gold workflow ran on a 400,000-row source prefix and a separate 418,374-row three-county extract. The 20-county pilot subsequently built scoped Parquet and extended history. The full-source scan established input integrity counts, while feature and label materialization was verified on the bounded cohorts. [Pipeline source](src/gridrescue/pipeline.py) · [Full-source scan](reports/full_development_audit.json) · [Three-county audit](reports/windows/county/audit.json) · [Expanded data audit](reports/modeling/county_expansion/DATA_AUDIT.md)

The existing Streamlit dashboard shows historical aggregates and filters. It can run with the small aggregate CSVs in the repository after dependency setup. The user-facing escalation prediction form is still pending. [Dashboard source](app/dashboard.py) · [Dashboard verification](reports/dashboard_verification.json)

## Review and reproduction

**Review from GitHub.** Open the three notebooks to inspect their saved outputs. The repository includes source, dependency pins, reports, figures and small reference fixtures, including the [100-row reload fixture](artifacts/modeling/development_reload_sample.parquet). The raw CSVs, generated Parquet stores, full archived row-level scores, native Windows Hadoop binaries and fitted model files are kept outside the review snapshot.

**Run locally.** The recorded Windows environment used Python 3.12.14, Java 17 and PySpark 3.5.3. From the project root, run `powershell -NoProfile -File scripts/setup.ps1 -InstallDependencies` to create the Windows environment and apply the PySpark worker patch. The setup script uses the version ranges in `requirements.txt`. The dependency lock records the versions for exact reproduction. In the project environment, run `python -m streamlit run app/dashboard.py` to open the historical dashboard. [Setup script](scripts/setup.ps1) · [Dependency lock](requirements-lock.txt) · [Windows Spark notes](reports/WINDOWS_NATIVE_SPARK_FIX.md)

**Rebuild the development inputs.** Obtain only the four **2018–2021** EAGLE-I CSVs and put them in `data/raw/`. Check hashes against the [source manifest](reports/source_manifest.json) and the [pinned archive reference](reports/modeling/cloud_expansion/source_manifest.json). The precise original download revision remains unverified. From the project root, with the project environment active and `src` on `PYTHONPATH`, the Windows Arrow-local path is:

```powershell
python scripts/make_sample.py
python scripts/extract_counties.py
python scripts/run_pipeline.py --storage arrow-local
python scripts/run_pipeline.py --scope county --storage arrow-local
python scripts/verify_persistence.py --storage arrow-local
```

The [notebook execution script](scripts/execute_notebooks.py) can run a notebook into a separate output directory. Executing Task 3 fits models. Scoring with the original frozen model requires the trusted local joblib file and its published metadata. Replaying the extension without fitting requires the exact archived development and OOF score files listed in the replay output. Full reproduction requires those local artifacts or the documented development rebuild. [Experiment reproduction](reports/modeling/local_improvement/REPRODUCE.md) · [Audit replay procedure](docs/ANTIGRAVITY_HANDOFF.md#environment-and-reproduction)

## Remaining work

- **Partial:** The historical dashboard and local inference helper exist. The validated inference interface, explanation display and course demo remain open.
- **Partial:** The Colab bundle and fixtures passed local preparation checks. Tier A Linux execution, checkpoint restore and resource measurements remain pending. [Cloud readiness](reports/modeling/cloud_expansion/READINESS.md)
- **Planned:** Agree on a controlled comparison and final selection protocol with the TA. The separately authorized, once-only 2022 evaluation remains pending. [Current project status](docs/CURRENT_PROJECT_STATUS.md)

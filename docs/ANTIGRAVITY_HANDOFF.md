# GridRescue handoff for Google Antigravity

Start in the GridRescue folder with [current project status](CURRENT_PROJECT_STATUS.md), the [Astra remediation plan](../reports/modeling/independent_audit/MASTER_REMEDIATION_PLAN.md), and the repository README. Use the existing environment and archived outputs for the first session.

## Purpose and architecture

GridRescue is a university ML and Big Data project that estimates whether an already positive county outage report will escalate in the following three hours. A positive label requires a recorded count at least as high as the anchor count plus the larger of 200 customers or 50% of the anchor count. Both classes require all 12 exact future quarter-hours, and the entire label window must end strictly inside its partition. Missing future slots leave outcomes unknown. Anchors can share a target window. The score describes escalation in this retrospective cohort.

| Area | Paths and interfaces |
|---|---|
| Data and features | `src/gridrescue/pipeline.py` reads EAGLE-I CSVs into Spark Bronze, cleans and quarantines into Silver, and builds past-only Gold predictors and separate label audits. `src/gridrescue/storage.py` handles native and bounded Arrow-local persistence. `reports/modeling/local_improvement/history.py` supplies the experimental extended history. |
| Official ML | `src/gridrescue/modeling.py` and `experiment.py` supply chronological evaluation and sklearn pipeline fitting. `notebooks/task1_eda.ipynb`, `task2_preprocessing.ipynb` and `task3_modeling.ipynb` are the executed canonical university notebooks. Existing output and rubric evidence is indexed in [notebook completion audit](../reports/NOTEBOOK_COMPLETION_AUDIT.md). |
| Frozen artifact | `artifacts/modeling/frozen_development_pipeline.joblib`, `reports/modeling/frozen_pipeline.json` and `reports/modeling/frozen_selection.json`. Keep the original Random Forest, its CV evidence and fixed 0.5 protocol intact. The official model was refit on 406,240 eligible development anchors across three counties after selection. |
| Experimental archive | `reports/modeling/county_expansion/pilot_20_20261121/cohort.json`, `reports/modeling/local_improvement/model_results/`, `reports/modeling/precision_diagnostic/results/` and `artifacts/modeling/local_improvement/{history,models}/`. Keep these identities and outputs intact. |
| Post-audit replay | `reports/modeling/precision_diagnostic/post_audit_evaluation.py` and `tests/test_post_audit_evaluation.py`. The evaluator checks FIPS, UTC quarter-hour keys, labels, purged periods, and archived score hashes. It reports rank metrics separately from frozen OOF decisions and summarizes county, state and spatial roles. |
| Cloud | `notebooks/colab_gridrescue_large_scale.ipynb`, `reports/modeling/cloud_expansion/{cloud_run,cloud_data,cloud_train,cloud_core,build_notebook,verify_preparation}.py`, the source, cohort and experiment manifests, and `tier_a_parity_reference.json`. |
| App and inference | `app/dashboard.py` reads historical aggregates from `reports/dashboard/{sample,county}/` and gates any final model evidence through `gridrescue.dashboard_data.load_model_result`. `gridrescue.inference.load_frozen_pipeline(root)` integrity-checks the official pipeline. `predict_escalation(pipeline, features)` validates the ordered 13 numeric predictors and returns class-1 scores and decisions. The dashboard has no live inference form or API. |

## Model and evaluation status

The official model remains the three-county Random Forest with 100 trees, depth 12, minimum leaf size 10 and a fixed 0.5 decision rule. Its archived 2021 selection AP is 0.523669 on its own development cohort. The experimental champion is the 120-tree, depth-6 CPU histogram XGBoost with 24 numeric predictors including UTC hour and training-fitted state encoding. It uses 1,053,328 eligible rows from 12 counties in 2018–2020 and has a keyed 2021 benchmark of 582,532 rows from 20 counties. Its archived AP is 0.4111679018, precision 33.99896%, recall 56.44882%, accuracy 68.88737% and 222.64185 FP rows per 1,000 eligible rows. Its incumbent strict cutoff is 0.2670107781887054, selected by maximizing accuracy subject to at least 60% recall on 890,035 chronological OOF rows. The archive also contains a distinct 60% OOF recall crossing policy.

The observed 2021 cohort has been consulted repeatedly. Describe it as development evidence and keep the different official and experimental populations explicit. The replay reports precision at descriptive 55% and 60% recall using entire score-tie groups. It reports the achieved recall in each slice. These descriptive coordinates supply no deployment cutoff. Use the frozen decisions for actual recall and false-positive burden. Geography includes the 12 seen counties, unseen counties in represented states, all represented-state counties, and the unseen New York cohort. Resample shared UTC 7- and 14-day blocks for paired archive comparisons. The intervals describe variation over these observed days and counties.

Astra verified weak ranking at recall-oriented thresholds, geographic transfer loss including after common-prior adjustment, and the contribution of low initial counts to missed escalations. UTC hour carries strong predictive signal and its physical versus reporting-cadence explanation is unresolved. Among 642,891 clean positive-current anchors in 2021, 60,359 lacked complete futures. The true outcomes of incompletely observed windows and any resulting population bias remain unresolved. No P0 count defect was verified. No candidate was newly fitted or promoted.

Flag runs join positive predictions within a county at exact 15-minute intervals. An unflagged row or missing quarter-hour starts a new run at the next flag. One hypothetical notification per run is a workload proxy. Rates use county-days with at least one eligible row and exposure also reports eligible quarter-hours converted to hours. “All-negative run” means every observed label in that run is negative. Label-run overlap is retrospective. Validating timely notifications requires independently timed crossing episodes and one-to-one matching. Physical outage incidents require separate ground truth.

## Environment and reproduction

Use the existing Windows `.venv` with Python 3.12.14, Java 17, PySpark 3.5.3, pandas 2.3.3, PyArrow 26.0.1 and scikit-learn 1.9.1. The CPU XGBoost 3.2.0 dependency is available through the existing project-local wheel environment for the experimental artifacts. See `requirements.txt`, `requirements-lock.txt`, `scripts/setup.ps1`, and the [Windows Spark repair](../reports/WINDOWS_NATIVE_SPARK_FIX.md). Installation on a new machine requires owner approval. The Windows PySpark worker backport and Hadoop-native configuration are described in the README and repair report. Keep the original environment and outputs available during transition.

From the GridRescue folder in PowerShell, use fresh output names for both JSON files.

```powershell
$env:PYTHONPATH = "$PWD/src"
$env:JUPYTER_PATH = "$PWD/.venv/share/jupyter"
$env:HADOOP_HOME = (Resolve-Path 'artifacts/windows-native-hadoop/hadoop-3.3.4').Path
$env:Path = "$(Join-Path $env:HADOOP_HOME 'bin');$env:Path"
$grPython = ".venv/Scripts/python.exe"
& $grPython -m pip check
& $grPython -m unittest discover -s tests -v
& $grPython -m unittest discover -s reports/modeling/local_improvement -v
& $grPython -m unittest discover -s reports/modeling/precision_diagnostic -v
& $grPython -m unittest discover -s reports/modeling/cloud_expansion -v
& $grPython reports/modeling/precision_diagnostic/post_audit_evaluation.py --output artifacts/antigravity_replay.json
& $grPython reports/modeling/cloud_expansion/verify_preparation.py --output artifacts/antigravity_colab_check.json
```

The replay defaults to 2,000 draws per block length. Set `--replicates 20` for a quick executable check and use the default for reported intervals. The evaluator needs the pinned champion and no-hour development score files, three OOF files per model, and existing small JSON manifests. It reads no raw CSVs and has no fit path. Cloud preparation verification additionally needs trusted local History Parquet partitions and saved models. `prepare_local.py --tier-a-parity-only --output <new-dir>` rebuilds only the bounded reference from pinned artifacts. Use `build_notebook.py` after changing packaged cloud files, then rerun `verify_preparation.py`. Existing artifact evidence and exact outcomes for this handoff are in [current project status](CURRENT_PROJECT_STATUS.md).

The app launches with `& $grPython -m streamlit run app/dashboard.py`. Use `scripts/reload_model.py` for the archived development reload proof after checking its documented output paths. Use `scripts/preflight.py --development-fixtures` to verify native writes on development fixtures in the intended final runtime. The handoff ran its underlying checks with the existing Hadoop binaries loaded in the process environment, preserving the archived environment report. Use separate staging output paths for any future notebook verification.

## Colab Tier A

Tier A is ready for an authorized Linux parity run. Linux execution, Drive quota, and actual peak memory still need verification. Approve and run only Tier A first. Follow the [Colab user guide](../reports/modeling/cloud_expansion/COLAB_USER_GUIDE.md) with Python 3.12, Java 17 and the pinned cloud requirements. Use one writer per Drive run. Confirm at least 10 GiB free Drive space and target 22 GiB free VM scratch. Pilot preprocessing enforces 7 GiB available RAM and 15 GiB scratch minimums. Each fit applies its width-dependent RAM and scratch checks.

Run the source and 82-row fixture checks, download only the four pinned development files after authorization, and require overall/per-county cohort and label equality. The full-checkpoint panel checks 115 training and 147 development rows for feature values and null masks across counties, state-hour, reporting-gap and severity groups. For each purged fold check fit/OOF identities. For final scoring require matching fitted preprocessing on the panel and exact same-runtime reload parity. The overall Windows incumbent tolerances are ±0.002 for AP, ±0.01 for precision, recall and accuracy, and ±10 FP rows per 1,000. Review cross-platform sample-score and per-state deltas as diagnostics. Reopen the same run from new scratch and verify a completed checkpoint before expansion. The notebook defaults all expensive stages to off.

Tier B/C require explicit owner authorization after Tier A. The existing tiers test combined county breadth and row volume on the same development evaluation cohort. A size-only claim would require same-geography and same-volume controls and a shared OOF policy panel. Stop at the last authorized feasible tier. Keep negative and inconclusive results.

## University deliverables and next priorities

1. **First Antigravity task.** Run the no-fit replay with a fresh output path and rerun the cloud preparation verifier. Compare the frozen metrics and protected hashes with this handoff. Read the [current status](CURRENT_PROJECT_STATUS.md) before using any training or final-evaluation entry point.
2. **Review the official evaluation gate.** Native Spark persistence and developmental fixtures passed in the configured Windows process. Recheck the same fixtures if the intended execution environment changes. Have the owner review the one-time official evaluation plan and its output/journal handling. The sealed year requires separate approval. If an authorized evaluation is interrupted, stop for owner review of the claimed journal.
3. **Complete the ML application.** Implement a validated current/past-input Streamlit flow around the frozen official pipeline. Derive the 13 inputs with exact temporal alignment, surface missing-history information, and display a score and explanation with scope and useful errors. Attach frozen final metrics only if the journal and reload proof pass. Finish the final ML submission and record a reproducible app demonstration.
4. **Close Big Data submission.** Confirm the 5–7 person roster and the supplied `docs/requirements/bigdata requirments.docx`. Verify historical dashboard KPIs, filters, data provenance and model-evidence presentation. Finalize the course report, setup and demo. The existing full development scan establishes ingestion and integrity. The saved scoped Spark results establish cleaning, feature and label processing for bounded cohorts.
5. **Resume experimental work only under an approved, small protocol.** Freeze endpoints and outer roles on earlier data. The least expensive next science question is whether a past-only reporting-cadence block adds ranking information on fixed folds and identical rows. Test future/other-county invariance, retain the original target, compare AP, matched-recall precision, frozen-policy burden and geography, and record a negative result if appropriate. Multi-state outer validation, first-crossing notification replay and target sensitivity remain separate projects.

## Git and artifact policy

At the time of this handoff, GridRescue had no project-root Git metadata and Git resolved to the parent home directory. The owner subsequently authorized a dedicated project repository for the [TA review snapshot](TA_PROGRESS_SUMMARY.md).

The review snapshot includes executed notebooks, source, tests, small provenance manifests, reference fixtures and review evidence. Raw inputs, generated data stores, fitted models, credentials, virtual environments, wheels and output archives are kept local. The reproduction commands above assume the original workspace and its archived inputs. See the [README](../README.md#review-and-reproduction) for the GitHub snapshot's prerequisites.

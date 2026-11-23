# Latest review revision ? 2026-11-17T17:19:11.866064+00:00

Task 1/2 focused improvements are executed and ready for personal review: **23 / 17 code cells**, no saved errors, all 30 scoped rubric items pass. See `TASK1_TASK2_FOCUSED_CHANGES.md`, `task12_focused_validation.json` and `task12_focused_execution.json`. Markdown indentation is fixed, both cohorts are explicit, the verified three-county summary is included, and fold-only preprocessing is explained. **Task 3 remains PAUSED pending explicit approval.** No classifier fitting, 2022 modeling access, system installation or Linux removal occurred. Older handoff details below are preserved as history.

---

# Current handoff ? Task 1/2 ready for user review

Updated 2026-11-17T16:48:43.849687+00:00. **HARD STOP: real-data Task 3 remains PAUSED until the user personally inspects and approves Tasks 1 and 2.** Do not run train_development.py, the Task 3 notebook, classifiers, CV, tuning or final evaluation. Do not remove Ubuntu/WSL/.venv-linux or change the frozen target/features/models/configuration.

- Final Task 1: 23 executed code cells, 9 saved and visually inspected plots. Final Task 2: 16 executed code cells. Clean kernels, no saved errors. `reports/task12_clean_kernel_execution.json` contains actual latest invocation evidence.
- Windows Arrow-local verification PASSED on both real development scopes. Prepared rows: prefix 163,386, counties 406,240. Exact schema/null/value/timestamp/content checks, original medians/means/sample stds and every reloaded vector matched. Missing-history rows exercised: prefix 21,597, counties 1,952.
- Native Hadoop writing remains BLOCKED. Complete suite: 40/41 passed, one unchanged native integration error. Do not suppress it or claim native repair.
- Arrow-local cap: 500,000 input rows, 8 export partitions, Arrow batches ?8,192. Larger-scale native persistence requires a separately verified Linux/native run. `.venv-linux` installation completed naturally; no Linux Spark persistence claim is made.
- Windows outputs: data/windows/{bronze,silver,gold}/<scope>, artifacts/windows/<scope>, reports/windows/<scope>. Prior paths, working memory notebooks, raw CSVs and checkpoints are preserved.
- A strict comparison caught 48 shifted county timestamps. UTC epoch transfer now avoids ambiguous Windows-local datetime conversion; the regression and full exact reruns pass. A bounded local commit retry preserves the old output on permanent failure. See WINDOWS_SPARK_DIAGNOSIS.md for full evidence.
- No real-data model artifacts, development scores, frozen model selection, final-evaluation journal or derived 2022 dataset exist. Task 3 has zero executed code cells. Earlier synthetic classifier unit tests are not real-data training. Four frozen source/approval hashes still match training_pause.json.

## Start the review here

1. notebooks/task1_eda.ipynb
2. notebooks/task2_preprocessing.ipynb
3. reports/NOTEBOOK_REVIEW_GUIDE.md
4. reports/TASK1_TASK2_RUBRIC_REVIEW.md
5. reports/TASK1_TASK2_CHANGE_SUMMARY.md
6. reports/WINDOWS_SPARK_DIAGNOSIS.md
7. reports/task12_review_validation.json and persistence_validation.json

The Windows environment is ready for these bounded Task 1/2 workflows. No dependency reinstall is necessary. For later authorized reproduction from this project root:

```powershell
.venv/Scripts/python.exe scripts/run_pipeline.py --scope sample --storage arrow-local
.venv/Scripts/python.exe scripts/run_pipeline.py --scope county --storage arrow-local
.venv/Scripts/python.exe scripts/verify_persistence.py --storage arrow-local
.venv/Scripts/python.exe scripts/execute_notebooks.py --mode arrow-local --notebook task1_eda --notebook task2_preprocessing --report reports/windows_notebook_execution.json
.venv/Scripts/python.exe scripts/verify.py tests
```

The last command still exposes the known native error. Native and Arrow-local backends are deliberately separate; use storage.load_preparation for JSON artifacts. The unexecuted Task 3 entrypoint still expects native Gold and has not been repointed; later integration awaits the user's revised requirements. No models may run merely because persistence is now verified. Historical notes below are retained and superseded by this section.

---

# Current control state ? training paused before first real-data fit

The latest user instruction pauses **all real-data classifier training, cross-validation, tuning and 2022 evaluation** until revised requirements arrive. Earlier training approval is superseded by this pause. Do not run `scripts/train_development.py`, `scripts/evaluate_final.py`, or the Task 3 notebook. Do not modify the approved target, thirteen features, three models, or experiment configuration.

The user permits finishing the already-running Linux environment installation and Task 2 persistence verification only. No reboot or unofficial Hadoop binaries are authorized. Windows notebooks are preserved at `artifacts/windows_notebooks/`; source/execution checkpoints remain in `artifacts/checkpoints/` and the notebook history folders.

**Current observed status:** No real-data model fits, CV/tuning results or final evaluation. Task 3 has ten unexecuted code cells. No `reports/modeling/development.json`, frozen selection, final evaluation journal, final predictions, or `data/final_test` exists. Earlier classifier tests used synthetic unit fixtures only. 2022 access remains limited to original inventory and parsed integrity counting, with no feature/label/model-development use. Machine-readable control record: `reports/training_pause.json`.

Linux WSL 2 / Ubuntu 24.04 is installed and starts successfully without a Windows reboot. Official Ubuntu OpenJDK 17 and Python venv prerequisites installed successfully. `.venv-linux` dependency installation is still active; PySpark wheel build completed. No Linux Parquet success is claimed yet. The older paused-session notes below are retained as historical context and are superseded by this section.

## Last observation at training pause

- `.venv-linux` pip installer was still running and writing packages; no failure or success was inferred from silence. It is allowed to finish naturally. Do not launch a duplicate setup process. The active tool session was `76120`; inspect actual live processes before relying on that historical identifier.
- Linux Spark preflight, Parquet round-trip, persisted scope pipelines and fresh-process preparation reload have **not yet run**. Task 2 persistence remains **UNVERIFIED**.
- Windows process inspection found setup launchers and no training/evaluation/notebook process. No real-data classifier was fitted. Earlier six modeling tests and two holdout-guard tests used synthetic fixtures only; two dashboard evidence tests used temporary reports.
- Current Task 1/2 source includes approved-status wording changes. Previously successful Windows notebooks are preserved under `artifacts/windows_notebooks/`; changed canonical cells require re-execution. Task 3 is unexecuted. Do not execute Task 3 while this pause is active.
- Current source syntax compilation completed successfully. No new model configuration changes were made after the pause request. Frozen code hashes are recorded in `training_pause.json`.

## Remaining permitted commands, after package installation finishes

From this project root in PowerShell, WSL commands require host access in this tool environment:

```powershell
wsl.exe -d Ubuntu-24.04 --cd (Get-Location).Path --exec .venv-linux/bin/python scripts/verify.py dependencies syntax layout preflight tests
wsl.exe -d Ubuntu-24.04 --cd (Get-Location).Path --exec .venv-linux/bin/python scripts/verify.py pipeline_sample pipeline_county persistence
```

These preparation pipelines fit only median imputation/scaling, with no predictive estimator, and read 2018?2021 subset CSVs only. `persistence` independently compares all saved scaled vectors with fresh-process reloaded Spark pipeline output. Stop on failures and report actual evidence. Task 3 notebook execution remains forbidden because it can initiate real-data training and final evaluation.

---

# GridRescue: paused-session handoff

**Project status: PAUSED by explicit user instruction on 2026-11-17.**

Do not resume execution, installations, model training or system changes until the user explicitly resumes this project. Do not restart, recreate the project, uninstall anything, change raw CSVs, or reboot Windows automatically. The only new project edit made for pausing was this handoff; the previously launched installer completed naturally and wrote its own completion log.

## Installer status at pause

The already-running elevated `scripts/install_wsl.ps1` operation finished at **2026-11-17 02:37:13 UTC** (04:37 Cairo). Its pre-existing queued steps both returned exit code 0:

1. Official Microsoft WSL bootstrap: **WSL 3.0.5 installed**.
2. **Ubuntu 24.04 LTS installed with `--no-launch`**.

The controller process has exited successfully. No new installation commands were initiated after the pause request. No reboot was issued. Ubuntu was **not launched** by the installer; Linux Python/OpenJDK prerequisites, `.venv-linux`, Linux notebook execution and Linux persistence remain **unverified/not performed**. Do not equate installation-command success with a working Linux Spark environment.

Authoritative evidence: `reports/wsl_installation.json`. `runtime_approval.json` was recorded before installation and still has `installation_verified: false`; the more recent installer log establishes command completion, not runtime readiness. A Windows Installer service process was visible during inspection; it was left alone, not killed or uninstalled. Do not use old process IDs to stop anything next session.

The original attempt using the uninstalled WSL bootstrap with distribution flags failed before installation. The subsequently approved, elevated two-step script succeeded. **Do not rerun the installer just because that earlier attempt failed.** First inspect the installed state after resuming.

## Preserve this exact workspace

- Project root: `C:\Users\Amr Hany\Downloads\GridRescue`.
- There is no project Git checkout; do not initialize/rebuild or discard files as a recovery shortcut.
- Original five CSVs: `data/raw/eaglei_outages_2018.csv` through `eaglei_outages_2022.csv`.
- Original PDFs: `docs/requirements/Task 1 for ML (1).pdf`, `Task 2 for ML.pdf`, `Task 3 for ML.pdf`. All five PDF pages were read directly this session.
- Existing implementation remains in `src/gridrescue/`, `scripts/`, `notebooks/`, `tests/`, `app/`; all reports and datasets are retained.
- Windows environment: `.venv` (Python 3.12.14, PySpark 3.5.3, Java 17). Preserve it as the working in-memory fallback.
- Future Linux environment: `.venv-linux` (not yet created). `.gitignore` already excludes it, `.venv`, data, artifacts and Parquet files.
- No unofficial Hadoop executables/DLLs were downloaded or installed.

### Verified checkpoint

`artifacts/checkpoints/20261116T235955/verified-project.zip`

SHA-256: `1EE05A40E79A349FE50EC2E131A500CA59E27583AEB2922095E2196C150F9B64`

The archive passed `ZipFile.testzip()` and contains 143 entries: code, notebooks, verified reports, documentation, tests and configuration as of the beginning of this continuation. It intentionally does not duplicate the multi-GB raw CSVs or virtual environments. Raw hashes are in `source_manifest.json` and `layout_migration.json`. Later working changes are present in the live workspace. Additional notebook/report/test-history backups remain under `artifacts/notebook_source_backups/`, `artifacts/report_history/`, and `artifacts/verification_history/`. Preserve all of them.

## Approvals already received; do not lose or silently broaden them

The user explicitly approved both decisions before pausing:

- **Runtime:** official WSL 2, Ubuntu 24.04 and required Linux Python/OpenJDK dependencies; separate `.venv-linux`; preserve Windows; no automatic reboot or unofficial Hadoop binaries. See `runtime_approval.json`.
- **Scientific target:** conditional GO for a university experiment using the existing three fixed counties and existing target/completeness/source policies. This is not operational validation. See `target_approval.json`.

The pause currently prevents further work despite those approvals. On an explicit resume, retain their exact scope; do not request the same scientific decision again unless the target/population would materially change.

Approved target/population:

- Los Angeles `06037`, Miami-Dade `12086`, Harris `48201`.
- Anchor must have a reported positive current count.
- Future escalation is a reported count reaching `current + max(200, 0.5 * current)` in `(t,t+3 hours]`.
- Both classes require all **12 exact future quarter-hours**. Incomplete outcomes stay unknown. Missing observations never become zero.
- Training: 2018-2020. Development validation: 2021.
- **2022 remains sealed from model development, tuning and model selection.** Its earlier integrity-only byte/hash/record count is documented; no test features, labels, model scores or tuning were generated.
- Choose the winner using development only, freeze choices, then evaluate 2022 once. No repeated held-out evaluation.
- Time-aware CV with at least a three-hour purge/embargo; all learned preprocessing refit within each training fold.

## Completed analytical work and actual measurements

### Original-source auditing

- Independent CSV parsing: **122,019,012 data records** across five files. Adding five headers gives the supplied **122,019,017** total. Every supplied annual total has the same one-header difference; the upstream author's methodology was not independently verified.
- Complete 2018-2021 Spark FAILFAST integrity audit: **96,222,547 records**, **6,618,821 invalid rows** under the shared rules. Reason flags overlap. Full-population deduplication, Silver/Gold materialization and labels were not run.
- All annual source maxima are December 31 at **00:00 UTC**, not the end of that calendar day. Account for this coverage edge.
- Evidence: `parsed_inventory.json`, `full_development_audit.json`, `source_manifest.json`.

### Real analytical scopes

| Scope | Raw | Invalid | Clean | Exact duplicate removals | Conflicting-key variants | Eligible train | Eligible validation |
|---|---:|---:|---:|---:|---:|---:|---:|
| January prefix | 400,000 | 66,369 | 333,631 | 0 | 0 | 109,785 | 53,601 |
| Three counties, full source dates | 418,374 | 1,434 | 416,940 | 0 | 0 | 303,791 | 102,449 |

Prefix invalids are missing-count tokens. County invalids are 1,336 invalid/missing counts and 98 off-grid times. These are scoped observations, not national rates. JSON evidence and real traces are in `reports/memory/sample/` and `reports/memory/county/`.

### Notebooks and Task 2

- **Task 1:** all **19 code cells** completed from a clean kernel, eight saved plots, real output and interpretations. Its existing memory cell was improved without adding/removing the successful cell sequence.
- **Task 2:** all **12 code cells** completed from a separate clean kernel. Numeric-only X has 13 predictors; categorical identifiers are excluded, so no categorical encoder is needed. Training-only imputation/scaling ran in memory.
- Actual transformed prefix dataset: **163,386 rows**, 13 features; **0 non-finite vectors and 0 dimension errors**.
- Evidence: `notebook_execution.json`, `notebook_output_review.json`, `preparation_memory.json`, `preparation_validation.json`, `FEATURE_DEFINITIONS.md`, and saved notebook outputs.
- Latest Task 1 memory measurements: Python driver RSS 160,694,272 bytes; Spark allocated cached blocks 7,889,120 bytes; bounded 1,000-row pandas frame 283,960 deep bytes. These are distinct scoped measurements, not whole-source or peak-cluster RAM. See `memory_usage.json`.
- Prefix training is January-only; its month feature has zero variance. The county feature audit measured 12 months, 24 hours and seven weekdays in every development year.
- **Spark Parquet and fitted Spark preprocessing save/reload have NOT succeeded yet.** Installation completion does not resolve this automatically.

### Expanded scientific audit

- `target_feasibility.json`: all **144 county-month-year groups** measured, all **12 county-years** exceed the predeclared 90% nominal reporting coverage threshold (actual range 97.76%-99.64%). No development county-year is removed by this qualification.
- Both classes occur in every monthly group; minimum monthly positives/negatives are **473 / 1,328**.
- **406,240** eligible development anchors. **405,438 (99.80%)** overlap the preceding eligible future window. They are not independent outage events.
- Included/excluded severity, completeness, overlap and a descriptive fixed-three-hour-cadence sensitivity were recorded. That sensitivity did not silently replace the quarter-hour modeling population.
- Eighteen real positive/negative/incomplete traces passed independent timestamp/count/threshold checks (`real_trace_checks.json`).
- See `TARGET_DECISION.md`, `target_eligibility_monthly.csv`, `target_eligibility_yearly.csv`. The decision text predates the user's approval and still says approval is required; `target_approval.json` and this handoff supersede that approval-status wording. Keep its measured evidence.

## Dashboard work completed

- Fixed the original data-source mismatch by producing new verified exports in `reports/dashboard/{sample,county}/daily.csv`, with hash/provenance manifests. Old `reports/memory/*/dashboard_daily.csv` exports are preserved.
- Found and fixed a real geographic aggregation issue: county name + state merged independent cities/counties (Baltimore, St. Louis), producing more than 96 observations in a supposed county-day. New exports aggregate by **FIPS/date**. Ambiguous geographic metadata is withheld, not arbitrarily selected; observation counts are retained. The two ambiguous prefix FIPS are `78030` and `78010`.
- Dashboard reads only verified FIPS exports and reconciles them to the matching audit. FIPS leading zeros remain strings. Independent-city selector labels distinguish FIPS.
- State/county/date/severity controls, four KPIs, charts, coverage limitations, actual selection findings and honest no-model status are implemented. No live-monitoring claim.
- **Five Streamlit AppTest tests pass**, including chart Arrow datasets checked against filtered source aggregates, empty results, scope switching and independent-city identity.
- Actual HTTP health endpoint returned **200**. The dashboard server was left running at `http://127.0.0.1:8501`; it was not stopped by the pause. Availability after the pause is not guaranteed; check before starting another server on that port.
- `dashboard_verification.json`, `verification/dashboard_tests.json`, `verification/dashboard.json` record functional verification.
- **Rendered browser visual inspection remains blocked/unverified.** Computer Use stopped because it could not determine the current Windows browser URL with sufficient confidence. No alternative UI automation bypass was used. AppTest/server success is not a claim that screenshots were visually reviewed.

Important: rerunning the parent memory audit changes its hash. If an export becomes stale, rerun `scripts/export_dashboard.py`; do not disable the provenance checks.

## Performance and test status

- `performance_comparison.json`: identical selected-county Spark aggregation, one warm-up pair excluded, three measured pairs in seeded randomized order; plans verified CSV versus in-memory scans.
- Uncached query mean 0.7430575 s (std 0.0858981); cached query mean 0.2787279 s (std 0.0311439). Mean cache construction 1.2757186 s is separately reported/excluded from cached query time. OS/JIT caches are uncontrolled; this is not a CSV/Parquet benchmark or a general cluster speedup claim.
- Last full baseline suite: **19 tests executed, 18 passed, one error**: `test_preparation_fits_only_training_and_saves_reload`, because native Windows Hadoop filesystem support is absent. It was not skipped/weakened. It checks in-memory train-only fitting before attempting the blocked save/reload.
- Five dashboard tests were added and passed **separately**. The combined **24-test suite has not yet been rerun**. Do not claim 24 green tests.
- Earlier dependency/syntax/layout checks passed; their recorded timestamps precede some latest scripts. Rerun them on resume.
- Raw logs retain upstream socket ResourceWarnings and Windows gateway-cleanup permission messages; successful notebook/functional checks returned exit code 0 despite those messages.
- Windows Python worker compatibility: `scripts/patch_spark_worker.py` applies Apache SPARK-53759's explicit socket-close backport to PySpark 3.5.3 source and worker ZIP in `.venv` only. Originals/hashes remain under `artifacts/runtime_patch/` and `spark_worker_backport.json`.
- Project-local setuptools 84.2.1 resolved `distutils` / `pyspark.ml` / `toPandas` imports. No model-related dependency installation is still pending in Windows.

## Work NOT done; exact remaining priorities

1. Launch/configure Ubuntu after explicit resume; verify whether Windows requires a manual restart. Do not automatically restart or rerun installation blindly.
2. Install Linux Python/OpenJDK prerequisites if absent, create separate `.venv-linux`, verify real Spark Parquet write/read and preprocessing save/reload, then rerun the full suite.
3. Complete Task 2 persistent source/Bronze/Silver/Gold/labels/prepared outputs for the existing scopes. Verify reload contents, not only file existence.
4. Adapt notebook execution to Linux without overwriting working Windows fallback notebooks. **Current `scripts/execute_notebooks.py` still explicitly uses `.venv/share/jupyter`**; `scripts/verify.py` was updated to use `sys.prefix/share/jupyter`, but the notebook runner itself still needs adjustment or the isolated execution command below.
5. Implement **all Task 3 predictive work**. No LR/RF/HGB classifier has been fitted. `task3_modeling.ipynb` remains the gated plan; no baseline/CV/tuning/winner/final-test/model artifact exists. Approval is now recorded, so resume with implementation, not another approval request for the unchanged target.
6. Continue dashboard model results only from genuine validated artifacts; preserve the functional historical view. Browser visual review remains separate.
7. Finish README, demo/presentation plan, beginner discussion guide, final report and acceptance refresh. `docs/FINAL_IMPLEMENTATION_PLAN.md` and `scripts/setup_linux.sh` exist; a demo plan has **not** been written yet.

The evidence matrix generator `scripts/update_acceptance.py` was created and run early in this continuation. `RUBRIC_EVIDENCE.md` / `FINAL_ACCEPTANCE.md` are **stale** relative to the later memory/dashboard/performance work and user approvals. It still marks all Task 3 rows FAIL and has a hardcoded overall incomplete status; extend it only as actual modeling evidence becomes available. Never convert unfinished model/storage items to PASS based on file existence.

`README.md`, `RUN_STATUS.md`, `FINAL_REPORT.md`, `LABEL_FEASIBILITY.md`, `TARGET_DECISION.md`, and `write_discussion_report.py` also include older “unapproved target” / old-dashboard wording. Refresh with measured results and the explicit approval record after resuming; preserve historical copies. The last generator does not yet cover this continuation's new functionality.

## Exact resume commands — do not execute while paused

### 1. Inspect the same project and installed runtime (PowerShell)

```powershell
Set-Location 'C:\Users\Amr Hany\Downloads\GridRescue'
Get-Content reports/NEXT_SESSION_HANDOFF.md
Get-Content reports/wsl_installation.json
Get-Content reports/target_approval.json
wsl.exe --status
wsl.exe --list --verbose
```

If Windows reports a restart requirement, let the user restart manually. Do not invoke reboot commands. Do not run `scripts/install_wsl.ps1` again just to resume an already installed distribution.

### 2. Open the installed distribution only after resume

```powershell
wsl.exe -d Ubuntu-24.04
```

The first launch may require the user to create a Linux account. Do not collect or automate password entry. Inside Ubuntu:

```bash
cd "/mnt/c/Users/Amr Hany/Downloads/GridRescue"
python3 --version
java -version
```

If prerequisites are missing, the user already approved these official Ubuntu dependencies, but the current pause must first be lifted:

```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jre-headless python3-venv
bash scripts/setup_linux.sh
export PYTHONPATH="$PWD/src"
export JUPYTER_PATH="$PWD/.venv-linux/share/jupyter"
.venv-linux/bin/python scripts/preflight.py
.venv-linux/bin/python -m unittest discover -s tests -v
```

Require successful Parquet and full-suite results before claiming persistence resolved. If these fail, diagnose the exact error; do not weaken the test, change the target, or install unofficial Hadoop binaries.

### 3. Materialize existing development scopes after successful Linux preflight

```bash
.venv-linux/bin/python scripts/run_pipeline.py
.venv-linux/bin/python scripts/run_pipeline.py --scope county
```

The first command writes prefix artifacts; the second writes county artifacts. Expected paths: `data/bronze/<scope>`, `data/silver/<scope>`, `data/gold/<scope>/{features,label_audit}`, and `artifacts/<scope>/{preparation,prepared_features}`. Existing raw CSVs and Windows `.venv` must remain unchanged. Back up current reports before commands that refresh them.

For Task 3 CV, start with **unimputed predictors** from county Gold/label-audit data and refit learned preprocessing inside each fold. Do not feed globally prepared vectors into CV. Keep only the explicit 13-feature allowlist; future diagnostics, y, identifiers and split metadata never enter X.

### 4. Preserve original Windows notebooks when checking Linux execution

After the persisted prefix pipeline succeeds, this isolated command executes copies and writes outputs under artifacts. It avoids the current notebook runner's Windows kernel path:

```bash
export GRIDRESCUE_STORAGE_MODE=parquet
.venv-linux/bin/python - <<'PY'
import json, os, sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
root=Path.cwd()
os.environ['JUPYTER_PATH']=str(Path(sys.prefix)/'share/jupyter')
os.environ['IPYTHONDIR']=str(root/'artifacts/ipython_linux')
os.environ['MPLCONFIGDIR']=str(root/'artifacts/matplotlib_linux')
out=root/'artifacts/linux_notebooks'
out.mkdir(parents=True,exist_ok=True)
results=[]
for name in ['task1_eda','task2_preprocessing']:
    notebook=nbformat.read(root/'notebooks'/f'{name}.ipynb',as_version=4)
    for cell in notebook.cells:
        if cell.cell_type=='code':
            cell.outputs=[]
            cell.execution_count=None
    client=NotebookClient(notebook,timeout=1800,kernel_name='python3',resources={'metadata':{'path':str(root)}})
    try:
        client.execute()
        code=[c for c in notebook.cells if c.cell_type=='code']
        assert all(c.execution_count is not None for c in code)
        assert not any(o.output_type=='error' for c in code for o in c.outputs)
        results.append({'notebook':name,'status':'VERIFIED','mode':'parquet','code_cells':len(code)})
    finally:
        nbformat.write(notebook,out/f'{name}.ipynb')
(root/'reports/linux_notebook_execution.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(results)
PY
```

This command is an unexecuted resume recipe, not evidence of Linux success. A failed copy may contain partial outputs. Do not replace the original fallback notebook with it. Task 3 must be implemented and actually executed separately after persistent preparation is verified.

### 5. Windows fallback / dashboard checks after resume

```powershell
$env:PYTHONPATH = "$PWD/src"
.venv/Scripts/python.exe scripts/inspect_notebooks.py
.venv/Scripts/python.exe scripts/verify.py syntax dependencies layout dashboard_tests
```

Check whether the existing local dashboard is still running:

```powershell
.venv/Scripts/python.exe -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=5).status)"
```

Only if it is not running, launch it once:

```powershell
.venv/Scripts/python.exe -m streamlit run app/dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false --server.fileWatcherType none
```

From a separate project-root terminal:

```powershell
.venv/Scripts/python.exe scripts/verify.py dashboard
.venv/Scripts/python.exe scripts/update_acceptance.py
```

If an audit was regenerated and export provenance is stale, run `scripts/export_dashboard.py` before the dashboard check. Do not rerun extraction/inventory/notebook-building scripts merely to resume; the existing data and successful outputs already exist. Do not run `build_notebooks.py` unless editing its templates intentionally; although it backs up and preserves unchanged outputs, changed cells require re-execution.

## First message when resuming

“Resume the existing GridRescue project from reports/NEXT_SESSION_HANDOFF.md. Preserve the Windows fallback and all results. WSL/Ubuntu installation commands already completed; verify Linux readiness and Task 2 persistence first. The unchanged three-county experiment is approved in reports/target_approval.json. Do not inspect 2022 until a development winner is frozen, and never reboot automatically.”


## Server recovery verification — 2026-11-18T11:22:17.197791+00:00

Recovered the existing workspace without rebuilding, reinstalling or refitting. Task 1 and Task 2 notebook hashes match the latest focused-review evidence; 23 and 17 code cells have sequential saved execution and zero errors. Dependency consistency, source syntax, canonical layout and three Markdown regressions passed freshly. Approved scientific configuration hashes still match the training pause record. No model/final-test artifacts exist; Task 3 remains paused for personal Task 1/2 review. Arrow-local persistence retains its prior exact verification; native Windows Hadoop persistence remains blocked. The historical full-suite result is 40/41 with the unchanged native integration error; it was not rerun because classifier tests are outside the current review scope. See recovery_validation.json for exact fresh versus historical evidence.

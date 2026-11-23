# Reproduce the isolated county expansion

Run from the GridRescue root in PowerShell with the existing Windows `.venv`. Choose a new run ID for an independent reproduction. Only the original 2018–2021 CSVs under `data/raw` are inputs. The scripts verify their recorded SHA-256 values. The earlier predictions are read only to verify the fixed 2021 comparison for the original three counties. [Windows Spark verification](../../WINDOWS_NATIVE_SPARK_FIX.md).

```powershell
$run = 'reproduction_20'
$python = '.\.venv\Scripts\python.exe'
$folder = 'reports/modeling/county_expansion'
& $python -m unittest discover -s $folder -v
& $python scripts/configure_windows_native_spark.py -- $python "$folder/prepare_cohort.py" coverage $run
& $python scripts/configure_windows_native_spark.py -- $python "$folder/prepare_cohort.py" prepare $run
& $python "$folder/train_cohort.py" $run
& $python "$folder/make_plots.py" $run
& $python "$folder/verify_run.py" $run
```

Run stages in order and inspect their exit codes. Coverage checkpoints a compact per-year table and freezes spatial roles before labeling. An interrupted coverage run can resume the remaining years with the original ID. Preparation checkpoints each year of extraction and each completed state. Persisted checkpoints use isolated paths and `errorifexists`. After a failed write that left an incomplete stage directory, inspect the stage before starting a new run or moving that directory to a distinct backup. Preserve old runs. No script overwrites the canonical model, notebooks, prepared datasets or reports.

`artifacts/modeling/county_expansion/<run ID>/` contains the native Parquet checkpoints, isolated Spark scratch and four experimental pipelines. `reports/modeling/county_expansion/<run ID>/` contains the cohort manifest, reconciled counts, configuration and model evidence. The resource plan is recorded before a pandas transfer. Training includes only the 12 seen counties and the final time comparison loads all 20 counties' 2021 rows. If required by available memory, the training transfer takes a fixed fraction within each county and UTC month based on a deterministic row-key hash. Such a run records the realized training population and keeps all 2021 comparisons paired.

`model_results/metrics.csv` contains per-period, per-geography and per-county metrics with absolute and relative differences against the numeric variant on identical rows. `cv_selection.json` records the highest mean AP on the three earlier time folds, independently of 2021 and the spatial holdouts. Verification recomputes the metrics from saved row-level scores and reloads all four expanded pipelines in a fresh process. The experiment has no 2022 evaluation step.

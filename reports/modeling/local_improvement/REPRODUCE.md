# Reproduce the 20-county local improvement experiment

Run from the GridRescue repository root in PowerShell. The experiment reuses the verified `pilot_20_20261121` Silver, labels and prediction files. It never reads the nationwide CSVs. It trains on the 12 existing seen counties and uses 2021 as previously consulted development evidence. The four unseen counties and four counties in unseen New York are evaluation groups. The 2022 dataset is outside this experiment.

## Setup and commands

Python 3.12.14, the existing GridRescue virtual environment, Java 17, and the verified native Windows Hadoop configuration are sufficient for the Spark and Random Forest phases. Install the CPU-only XGBoost wheel into the experiment directory once. The command leaves the virtual environment’s installed packages alone.

```powershell
.\.venv\Scripts\python.exe -m pip download --only-binary=:all: --no-deps --no-cache-dir --dest artifacts/modeling/local_improvement/wheels xgboost-cpu==3.2.0
.\.venv\Scripts\python.exe -m pip install --no-index --no-deps --target artifacts/modeling/local_improvement/deps_local artifacts/modeling/local_improvement/wheels/xgboost_cpu-3.2.0-py3-none-win_amd64.whl
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe scripts/configure_windows_native_spark.py -- .\.venv\Scripts\python.exe -m unittest discover -s reports/modeling/local_improvement -v
```

The [PyPI Windows x64 CPU wheel](https://pypi.org/project/xgboost-cpu/3.2.0/#files) used here had SHA-256 `bfe72e42f73d2c6870a1a8b75324d56ae86ddad9abd4dccefeb36f2c3196dd48`. The loaded build reported `USE_CUDA=False`.

The commands below write to new destinations. Choose an unused suffix for a subsequent run. Run Spark and training sequentially to keep the Spark JVM and scikit-learn matrices from competing for RAM.

```powershell
$report = 'reports/modeling/local_improvement'
$artifact = 'artifacts/modeling/local_improvement'
.\.venv\Scripts\python.exe "$report/thresholds.py" --output "$report/threshold_results_repeat"
.\.venv\Scripts\python.exe scripts/configure_windows_native_spark.py -- .\.venv\Scripts\python.exe "$report/history.py" --destination "$artifact/history_repeat"
.\.venv\Scripts\python.exe -u "$report/train_local.py" --history "$artifact/history_repeat" --output "$report/model_results_repeat" --models "$artifact/models_repeat"
```

Training can reuse complete OOF checkpoints in the same output directory before selection has been written. The run rejects a folder after the selection is locked. The Spark job checks for at least 2.5 GiB available RAM. Training checks for 2.25 GiB available RAM before collecting the bounded cohort and both check for 2 GiB free disk. The measured resource records are in the Spark audit, training configuration, and per-fit files. The Spark stage uses a 2 GiB driver, four shuffle partitions and one state at a time. Forest training and XGBoost use two threads. The model runner keeps original features in their trained order, then appends historical features before the geography blocks. It does not sample the training or evaluation populations.

## Reading the code

- In `thresholds.py`, sorting puts larger scores first. A cumulative count adds true positives as the cutoff drops. The sweep moves tied scores together because a single cutoff cannot separate them. The experiment compares `float64` scores against the saved, full-precision cutoff. Equality counts as a negative.
- In `history.py`, `Window.partitionBy` separates counties and `orderBy` sets the clock. `rangeBetween` compares epoch seconds and `over` applies a calculation to that time range. `withColumn` adds a derived column. The join matches the new fields to the original label using FIPS and timestamp.
- In `train_local.py`, `Pipeline.fit` learns the imputer, scaler, category vocabulary and classifier on one training block. `predict_proba` applies those transformations with the fitted statistics. A missing history value stays missing until the training-fitted imputer fills it. FIPS stays a five-character string. `handle_unknown='ignore'` provides a zero indicator block for unseen labels.
- `selection.json` is written before 2021 is loaded by the modeling stage. It records the model choice from mean chronological fold AP and every cutoff chosen from pooled OOF. A score-dependent cutoff is stored at full precision.

**TA question. Why can a Jan. 1 feature use Dec. 31, while some Dec. 31 training labels are purged?** The feature can use reports that already exist at the prediction timestamp. A training label looks forward three hours, so it is excluded when that future can cross into the next evaluation partition.

**TA question. Can a new cutoff improve average precision?** No. AP depends on probability rankings across all cutoffs. The selected cutoff changes the confusion matrix and therefore decision metrics such as recall, F1 and false alarms.

Machine-readable evidence for this run is in [threshold_results](threshold_results/) and [model_results](model_results/). The augmented native Parquet and saved candidate models are under `artifacts/modeling/local_improvement/`. The frozen official model, its prediction threshold and the canonical notebooks are separate.

## Verification from the completed run

| Check | Result |
| --- | --- |
| Local-improvement fixtures | 10 passed in 39.8 seconds |
| Existing GridRescue suite | 46 passed in 163.3 seconds |
| Native history write and read | 1,635,860 eligible anchors reconciled across all five states |
| Fresh Python reload | Identical scores on 585 saved 2021 observations per new pipeline |
| Prediction evidence | All 582,532 2021 keys and labels aligned, 18 OOF candidate-fold files and 36 overall metric rows verified |
| Artifact preservation | Eight protected official hashes and four archived expansion forest hashes matched |

Spark emitted socket warnings and Windows printed an `Access denied` line after Spark shutdown. Both test commands exited with code 0. The native Spark write and reload checks passed.

[Machine-readable verification](model_results/verification.json)

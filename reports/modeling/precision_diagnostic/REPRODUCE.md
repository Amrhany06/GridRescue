# Reproduce the local precision diagnostic

Run these commands from the GridRescue repository root in PowerShell. Use the existing `.venv` and the CPU-only XGBoost 3.2.0 already installed under `artifacts/modeling/local_improvement/deps_local`. The input is the archived 20-county pilot described in the [local improvement reproduction guide](../local_improvement/REPRODUCE.md). The diagnostic reads only precomputed development scores, model files and processed history partitions. It uses pandas and PyArrow for data reads and requires no Spark session or download.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$py = '.\.venv\Scripts\python.exe'
$report = 'reports/modeling/precision_diagnostic'
$work = 'artifacts/modeling/precision_diagnostic'
New-Item -ItemType Directory -Force $work | Out-Null
$env:MPLCONFIGDIR = (Join-Path (Resolve-Path $work).Path 'mpl-cache')
& $py -m unittest discover -s $report -v

# Reproduce the published metrics and figures without fitting.
& $py -u "$report/diagnostic.py" --output "$work/replay_example" --reuse-ablation "$report/results"
& $py "$report/verify.py" "$report/results" "$work/replay_example" "$work/verification_example.json"

# Optional full reproduction. Only the hour-omitted XGBoost is fitted.
& $py -u "$report/diagnostic.py" --output "$work/fit_example"
& $py "$report/verify.py" "$work/fit_example" "$work/replay_example" "$work/refit_verification_example.json"
```

Choose unused output directory names for each run. Run one process at a time. The initial resource checks require at least 2.25 GiB of available RAM and 2 GiB of free disk. The CPU booster uses two threads. The optional fit performs three fold fits and one final fit, with no parameter search. `diagnostic.py` writes the OOF-only threshold file before it reads 2021. `verify.py` compares emitted files, independently recomputes the pooled, development, geographic and 2021 hourly results, and checks that moving each OOF cutoff one floating-point step higher would miss its recall target.

## Output guide

| File | Contents |
| --- | --- |
| [frozen_thresholds.json](results/frozen_thresholds.json) | Full-precision OOF-only cutoffs and the pre-existing incumbent cutoff |
| [oof_metrics.csv](results/oof_metrics.csv) | Pooled and individual fold metrics |
| [development_metrics.csv](results/development_metrics.csv) | Identical-row 2021 metrics for all models, rules, geographic groups and counties |
| [development_matched_recall.csv](results/development_matched_recall.csv) | Descriptive curve precision at fixed recall coordinates, with no cutoffs |
| [hourly_metrics.csv](results/hourly_metrics.csv) | Overall, state and county hourly results for each fold and for 2021 |
| [hour_conditional_permutation.csv](results/hour_conditional_permutation.csv) | AP after county-month hour shuffles on a fixed diagnostic sample |
| [archived_hour_permutation.json](results/archived_hour_permutation.json) | Reused overall 2021 hour-permutation evidence |
| `pr_*.parquet` | Every distinct score block on the plotted precision–recall curves |
| `ablation_oof_*.parquet`, `ablation_2021.parquet`, `ablation.joblib` | Row-keyed ablation scores and local experimental pipeline |
| [run_evidence.json](results/run_evidence.json) and [verification_extended.json](verification_extended.json) | Row counts, checksums, configuration, resource measurements and verification |

The `.joblib` file is a local research artifact. Load it only from a trusted copy of this workspace. The four archived variants are scored from their saved prediction files. Model reload checks use 585 rows for each archived model and every 2021 row for the ablation. The archived original forest can change by a few units of floating-point roundoff when its threads sum trees in a different order. Its check uses the earlier archive’s absolute tolerance of `1e-14`. The analyses use the archived scores at full precision.

The published run resumed from four completed ablation fits after correcting the archived forest reload check. The fit-by-fit resource trace from the initial process is unavailable. The completed analysis recorded a peak Python working set of 1.31 GiB, a minimum of 4.60 GiB of available system RAM, and 7.42 GiB of disk free at the end. The independent replay used the same ablation model and prediction files in a fresh process and fitted zero models.

## Verification from this run

| Check | Result |
| --- | --- |
| Precision diagnostic tests | 7 passed |
| Existing GridRescue suite | 46 passed |
| Existing local-improvement suite | 10 passed |
| Independent OOF and 2021 recomputation | 32 overall metric rows, 400 geographic metric rows, 1,872 hourly rows, and 15 OOF threshold decisions |
| Output replay | 26 byte-identical results, including all four figures |
| Artifact integrity | 16 protected artifact hashes matched, including all three task notebooks and the official model |

The two existing Spark suites exited successfully and emitted launcher and cleanup diagnostics also seen in the prior experiment. The diagnostic scripts ran without Spark. Their input hash manifest lists the bounded feature partitions and score files from 2018–2021. No 2022 files were opened.

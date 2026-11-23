# Four-variant Random Forest comparison

Every fit used the existing 100-tree forest, depth 12, minimum leaf size 10, seed 17, two workers, the same eligible rows, and the same 13 numerical features. Scikit-learn fitted median imputation, scaling and any one-hot encoder only inside the relevant training partition. Each added geographic field used five-character string FIPS or the source state name. The class decision stayed `score > 0.5`. The forest's approved `max_features='sqrt'` setting remained fixed. The resulting number of candidate predictors per split varies with encoded width, so the observed effect includes that consequence of adding columns.

## Chronological development cross-validation

| Evaluation interval | Earlier training rows | Validation rows | Positive prevalence | Numeric AP | State AP | FIPS AP | Both AP |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2018 H2 | 163,273 | 181,267 | 24.73% | 0.377135 | 0.423192 | 0.450326 | 0.455737 |
| 2019 | 344,560 | 358,402 | 24.18% | 0.373257 | 0.440413 | 0.468047 | 0.470752 |
| 2020 | 702,962 | 350,366 | 24.59% | 0.373834 | 0.435196 | 0.472465 | 0.475653 |
| **Mean ± sample SD** | | | | **0.374742 ± 0.002092** | **0.432933 ± 0.008830** | **0.463613 ± 0.011717** | **0.467380 ± 0.010377** |

The mean paired AP gains over numeric were +0.058192 for State, +0.088871 for FIPS, and +0.092639 for both. The paired gains' sample SDs were 0.010901, 0.013714, and 0.012347 respectively. All geographic additions improved the pooled AP in each fold. Both led FIPS by only 0.003768 mean AP. The folds share earlier data, their outcomes overlap in time, and the ranking is descriptive.

The development candidate was frozen as **both** from mean AP on these 12 training counties only, before scoring 2021 or either spatial holdout. The prediction target, row eligibility, exact-time lags, three-hour embargo and previous model remain unchanged. [CV selection record](pilot_20_20261121/model_results/cv_selection.json).

## 2021 scores on the same 582,532 expanded rows

All four comparison forests fitted all **1,053,328** eligible 2018–2020 anchors from the 12 seen counties. This mixed 2021 population includes the eight geographic holdouts. Its positive prevalence was **20.3173%**.

| Variant | AP | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| 13 numeric | 0.324024 | 0.796966 | 0.539130 | 0.004715 | 0.009348 | 0.660658 |
| + State | 0.400952 | **0.806668** | **0.706327** | 0.082912 | 0.148403 | **0.691907** |
| + FIPS | 0.394356 | 0.804018 | 0.632993 | 0.084230 | 0.148676 | 0.686682 |
| + State and FIPS | **0.402954** | 0.805896 | 0.658487 | **0.092730** | **0.162566** | 0.685008 |

| Variant | Absolute AP change | Relative AP change | Confusion matrix `[TN, FP, FN, TP]` |
|---|---:|---:|---|
| 13 numeric | — | — | `[463700, 477, 117797, 558]` |
| + State | +0.076928 | +23.74% | `[460097, 4080, 108542, 9813]` |
| + FIPS | +0.070331 | +21.71% | `[458397, 5780, 108386, 9969]` |
| + State and FIPS | +0.078929 | +24.36% | `[458485, 5692, 107380, 10975]` |

Relative changes divide by the numeric result on the same rows. The [full metrics table](pilot_20_20261121/model_results/metrics.csv) includes both absolute and relative changes for all six metrics in every cohort, county and period. A zero reference leaves the relative result undefined. The combined model's 9.27% recall is low at the fixed threshold despite its AP gain. State-only led accuracy, precision and ROC-AUC.

## Same-row check against the previous three-county models

| Feature set | Previous 3-county training AP on original 2021 rows | Expanded 12-county training AP on those rows | AP change | Relative change |
|---|---:|---:|---:|---:|
| Numeric | 0.523669 | 0.490470 | −0.033199 | −6.34% |
| + State | 0.578607 | 0.565505 | −0.013102 | −2.26% |
| + FIPS | 0.578607 | 0.569376 | −0.009231 | −1.60% |
| + State and FIPS | — | 0.566411 | — | — |

The three matched comparisons all declined on the original 102,449 validation rows. Expanded training kept all 303,791 original eligible training rows and added 749,537 from nine other counties. This measures the effect of that additional geography and data mix. The State and FIPS vocabularies also expanded. The combined variant has no matching three-county fit, and its AP is below the earlier geographic benchmark on those same rows. [Exact historical keys, feature parity and benchmark metrics](pilot_20_20261121/model_results/historical_comparison.json).

## Complexity, generalization gap and compute

| Variant | Encoded features | Candidate features per split | Total fitted tree nodes | Train AP | 2021 seen AP | AP gap | Fit seconds | Peak Python RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 numeric | 13 | 3 | 405,812 | 0.415372 | 0.361618 | 0.053753 | 133.93 | 1.55 GiB |
| + State | 17 | 4 | 423,114 | 0.479893 | 0.438562 | 0.041331 | 141.87 | 1.63 GiB |
| + FIPS | 25 | 5 | 325,358 | 0.510459 | 0.446470 | 0.063990 | 153.57 | 1.63 GiB |
| + State and FIPS | 29 | 5 | 344,726 | 0.509726 | 0.450123 | 0.059603 | 117.49 | 1.64 GiB |

All final trees reached depth 12. Train-to-later gaps reflect both fitting and potential year-to-year distribution change. The 12 CV fits took **454.5 seconds** in total and the four comparison fits **546.9 seconds**. End-to-end Python modeling, including scoring and persistence, took **1,119.7 seconds**. The pre-transfer workspace estimate was **1.65 GiB** with **3.83 GiB** available. The lowest sampled available system RAM during fitting was **1.69 GiB**. RSS was sampled at 250 ms intervals and can miss brief peaks. The run used the full selected rows without sampling. Single-run timings do not establish a speed advantage. [Resource plan](pilot_20_20261121/model_results/resource_plan.json), [all fit measurements and model hashes](pilot_20_20261121/model_results/execution.json).

Four expansion tests and six shared modeling tests passed. Fresh-process verification recomputed 296 metric rows and their deltas from stored scores, and reloaded all four experimental pipelines against 100 saved scores each. It also checked that the canonical model artifacts and notebooks retain their hashes. The experimental pipelines are under `artifacts/modeling/county_expansion/pilot_20_20261121/models/`. The 2022 holdout remains sealed. [Independent verification](pilot_20_20261121/model_results/independent_verification.json).

[AP plots](pilot_20_20261121/model_results/geographic_comparison.png) · [Geographic generalization](GENERALIZATION_REPORT.md) · [Reproduce](REPRODUCE.md)

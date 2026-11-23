# Geographic feature experiment

**Baseline reproduction: PASS.** A fresh fit with the unchanged 13-feature contract reproduced 2021 average precision (AP) of **0.5236688442307188** on the same 102,449 rows and labels. The AP difference was zero, and the largest individual score difference from the saved predictions was 3.33 × 10⁻¹⁶. Adding either location field raised pooled 2021 AP to **0.57860677** and improved AP across all three chronological folds. The benefit varied by county. [Baseline reproduction](run_20261121T170253377051Z/baseline_reproduction.json).

## Comparison protocol

All three variants used the same verified 406,240 eligible development anchors, unchanged 12-slot target, ordered numeric predictors, expanding time folds and three-hour purge. Final comparison fits used 303,791 eligible 2018–2020 anchors. The 2021 results are a fixed, previously used development comparison on three seen counties. Every forest retained 100 trees, maximum depth 12, minimum leaf size 10, seed 17 and two workers. The class threshold was score `> 0.5`, with exact ties assigned class 0.

Each fit learned the original numeric median imputation and scaling on its training partition. Geographic variants appended either `state` or five-character string `fips_code`. `OneHotEncoder(handle_unknown='ignore')` fitted within the same training partition. An unseen state or county produces an all-zero geographic block. No chronological evaluation row contained an unseen category. The focused tests verified both unknown-category cases. [OneHotEncoder documentation](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html), [run configuration and fold boundaries](run_20261121T170253377051Z/execution.json).

## Chronological CV within 2018–2020

| Fold | Train / validation rows | Validation prevalence | Baseline AP | State AP | FIPS AP | Paired AP gain, either variant |
|---|---:|---:|---:|---:|---:|---:|
| 2018 H2 | 48,860 / 50,935 | 0.372632 | 0.524221 | 0.572093 | 0.572093 | +0.047872 |
| 2019 | 99,801 / 101,349 | 0.362786 | 0.548634 | 0.606261 | 0.606261 | +0.057627 |
| 2020 | 201,150 / 102,641 | 0.371041 | 0.548011 | 0.605419 | 0.605419 | +0.057408 |
| Mean ± sample SD | | | 0.540289 ± 0.013919 | 0.594591 ± 0.019488 | 0.594591 ± 0.019488 | +0.054302 ± 0.005570 |

The smallest paired gain was 0.047872, larger than the AP sample SD across folds for either feature set. All three gains were positive and 2021 moved in the same direction. This is a material descriptive gain within the tested cohort. The folds share training history and the 15-minute rows have overlapping outcome windows. Three folds do not support a reliable significance claim.

| Variant | CV mean accuracy | CV mean precision | CV mean recall | CV mean F1 | CV mean ROC-AUC | Total CV fit seconds |
|---|---:|---:|---:|---:|---:|---:|
| 13 numeric | 0.666070 | 0.573778 | 0.391605 | 0.461010 | 0.674108 | 28.81 |
| + State | 0.682823 | 0.595047 | 0.460836 | 0.515834 | 0.707421 | 27.02 |
| + FIPS | 0.682823 | 0.595047 | 0.460836 | 0.515834 | 0.707421 | 26.74 |

Fit timing includes preprocessing and training. This single local run provides runtime observations, with no repeat measurements to establish a speed advantage. [All fold results and confusion matrices](run_20261121T170253377051Z/metrics.csv), [fold means and sample SDs](run_20261121T170253377051Z/cv_summary.csv).

## Fixed 2021 development comparison

All variants scored the same 102,449 rows with 33,719 positives. The positive prevalence baseline for AP was 0.329130.

| Variant | AP | Accuracy | Precision | Recall | F1 | ROC-AUC | Fit seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| 13 numeric | 0.523669 | 0.694189 | 0.555319 | 0.355616 | 0.433577 | 0.683227 | 22.68 |
| + State | 0.578607 | 0.706888 | 0.573447 | 0.427207 | 0.489641 | 0.715858 | 24.54 |
| + FIPS | 0.578607 | 0.706888 | 0.573447 | 0.427207 | 0.489641 | 0.715858 | 21.91 |
| Change from baseline, either variant | +0.054938 | +0.012699 | +0.018129 | +0.071592 | +0.056064 | +0.032631 | |

The pooled `[TN, FP, FN, TP]` counts changed from `[59128, 9602, 21728, 11991]` to `[58015, 10715, 19314, 14405]`. Either location variant caught **2,414 more positives** and produced **1,113 more false positives**.

| 2021 county | Rows | Positive prevalence | Baseline AP | Geographic AP | AP change | Recall change | F1 change |
|---|---:|---:|---:|---:|---:|---:|---:|
| Los Angeles `06037` | 34,476 | 0.429864 | 0.647098 | 0.691710 | +0.044612 | +0.271390 | +0.187665 |
| Miami-Dade `12086` | 34,057 | 0.296943 | 0.473929 | 0.477644 | +0.003715 | −0.177000 | −0.119091 |
| Harris `48201` | 33,916 | 0.259052 | 0.477040 | 0.474666 | −0.002374 | +0.020715 | +0.011669 |

| County | Baseline `[TN, FP, FN, TP]` | State and FIPS `[TN, FP, FN, TP]` |
|---|---|---|
| Los Angeles | `[18302, 1354, 10751, 4069]` | `[15125, 4531, 6729, 8091]` |
| Miami-Dade | `[19793, 4151, 5865, 4248]` | `[22050, 1894, 7655, 2458]` |
| Harris | `[21033, 4097, 5112, 3674]` | `[20840, 4290, 4930, 3856]` |

County-macro AP rose from 0.532689 to 0.548007, a gain of 0.015318. The larger pooled gain can partly reflect better ranking between counties with different escalation rates. The county mean CV AP changes were +0.056101 in Los Angeles, −0.005465 in Miami-Dade and +0.009774 in Harris. Los Angeles had the largest 2021 gain, with precision falling by 0.109299 at the fixed threshold. Miami-Dade's small AP gain was accompanied by a large recall loss, and Harris's 2021 AP slipped. Full per-county metrics, prevalence, differences and confusion matrices are saved for each fold and variant. [Complete metrics](run_20261121T170253377051Z/metrics.csv), [paired AP plot](run_20261121T170253377051Z/paired_ap.png).

## Interpretation and next step

California ↔ Los Angeles, Florida ↔ Miami-Dade and Texas ↔ Harris form a one-to-one mapping. Their encoders produced identical indicator columns in the same order. State and FIPS scores agreed within 3.33 × 10⁻¹⁶ across every scored anchor and had identical classifications. The experiment cannot establish their relative utility or geographic generalization. The unchanged forest setting `max_features='sqrt'` also changes the nominal candidate count from three to four when the input grows from 13 to 16 features. The measured effect therefore covers the feature addition and its effect on the forest's split sampling. [Random Forest documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html).

**Further geographic evaluation is justified.** The gain warrants a separately authorized coverage audit and 20-county pilot with multiple counties per state, unseen counties in seen states, and a whole-state holdout. The expansion plan includes a 15-county fallback, measured Windows resource gates and verified coverage-based sizing. The frozen model and canonical notebooks retain their recorded hashes. The 2022 holdout remains sealed. [Expansion plan](EXPANSION_PLAN.md).

## Reproduce this run

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s reports/modeling/geography_experiment -p test_experiment.py -v
.\.venv\Scripts\python.exe reports/modeling/geography_experiment/run_experiment.py
```

The four focused tests passed. The runner creates a unique output directory, gates geography fits on baseline reproduction, and saves one Parquet score file per evaluation period. The run stores scores, configuration and metrics. Model binaries remain part of the canonical development run only.

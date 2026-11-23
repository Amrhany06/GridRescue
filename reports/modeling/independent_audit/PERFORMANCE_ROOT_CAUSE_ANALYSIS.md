# Why the champion raises false positives and misses escalations

The decision unit is an eligible 15-minute county row. Positive means a recorded crossing in the next 12 slots. All numbers below come from aligned 2021 scores, history and reconstructed future observations. Future values are used only to audit outcomes.

## Independent score replay

`reports/modeling/local_improvement/model_results/predictions_2021.parquet` SHA-256 9e60d50cf5b330c01fd3c1a97bf1bfba08acae9fdb0a3d52f203abc321e00b8a. Join the no-hour predictions from `reports/modeling/precision_diagnostic/results/ablation_2021.parquet` (dbd67d6a6d879311e040af5929e1ded02eb355e712c1b3ada5764fff7e363f5f) on FIPS and UTC time with uniqueness and binary-label equality required. Cast scores to float64 **before** strict comparison. Use sklearn average precision (sum of precision times recall increments).

| Decision | Recorded escalation | Recorded negative |
|---|---:|---:|
| Flag | 66,810 | 129,696 |
| No flag | 51,545 | 334,481 |

AP 0.4111679018, ROC AUC 0.700933, precision 0.339989619, recall 0.564488192, accuracy 0.688873744. The 222.641846 FP per 1,000 use every eligible row as denominator. FPR among negatives is 27.94%. Constant negative would earn 79.68% accuracy and zero recall. With prevalence 20.32%, FP = 464,177 negatives × 27.94% overwhelms TP = 118,355 positives × 56.45%. This accounts arithmetically for the low PPV. The following evidence explains why the scores make that tradeoff.

## Where the errors are

| Customers out at anchor | Rows | Prevalence | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| 1–50 | 251,679 | 15.35% | 29,160 | 24,035 | 33.35% | 37.77% |
| 51–200 | 162,356 | 22.93% | 44,123 | 14,911 | 33.59% | 59.95% |
| 201–400 | 61,297 | 28.56% | 24,291 | 3,994 | 35.74% | 77.18% |
| 401–1,000 | 53,436 | 27.57% | 21,800 | 3,694 | 33.62% | 74.93% |
| >1,000 | 53,764 | 19.09% | 10,322 | 4,911 | 34.15% | 52.15% |

**STRONGLY SUPPORTED — small baselines and weak momentum identify hard cases.** The smallest band contributes 46.63% of misses. At current=50 the outcome requires at least a fivefold total count; at 400 and above it requires 1.5×. A zero 60-minute net change has 33.97% recall (8,205 misses), versus 60.53% for positive change and 57.72% for negative change. A flat observed one-hour history (variance <1e-8) occurs in 14.06% of FN versus 5.99% of TP. These are marginal associations. County mix, severity and hour covary. Most missed positives still had non-flat history. Discriminate via within-county/hour/severity comparisons and matched outer-fold feature ablations (E3).

**NOT SUPPORTED — missing recent history explains most misses.** Full historical coverage yields 56.71% recall versus 53.22% on 46,129 incomplete-history rows. Fully observed history accounts for 47,390 of 51,545 misses (91.94%) and 120,237 of 129,696 FP. Missing the exact 60-minute lag even yields 59.03% recall. There could be stronger selection among future-incomplete rows outside this denominator. Coverage review E1 addresses that separate question.

**NOT SUPPORTED — most errors are threshold-edge label noise or immediate surprises.** Define margin as (largest future count − current)/max(200, 0.5 × current). FP median margin is 0.080, 30.71% had no net peak increase and only 5.76% reached [0.8,1) of the required rise. FN median margin is 2.91, versus 3.54 for TP. Only 10.09% of FN crossed at the first future slot versus 10.98% of TP. This rules against an excess of immediate crossings among misses on this measure. An unobserved shock later in the window remains plausible. The dataset supplies no physical-event ground truth. A sustained-target sensitivity and as-of weather comparison are E5 and E6.

## Score distributions and policy

| Score range (upper inclusive) | Rows | Mean score | Observed positive rate |
|---|---:|---:|---:|
| 0–0.10 | 74,042 | 0.078 | 0.069 |
| 0.10–0.20 | 212,686 | 0.148 | 0.126 |
| 0.20–incumbent cutoff | 99,298 | 0.231 | 0.197 |
| Cutoff–0.35 | 87,765 | 0.306 | 0.253 |
| 0.35–0.50 | 83,677 | 0.413 | 0.348 |
| 0.50–0.70 | 20,513 | 0.566 | 0.565 |
| Above 0.70 | 4,551 | 0.747 | 0.855 |

**VERIFIED — overlap and a recall-oriented rule drive FP volume.** Median scores were 0.349 FP, 0.399 TP, 0.179 FN and 0.149 TN. In the first bin above the cutoff roughly three of four flags are negative. The mean score across all rows is 0.2345 versus prevalence 0.2032, Brier 0.1468. Reliability even reverses direction in the top bin. A single global intercept may be insufficient. Monotone calibration can improve probability interpretation and transfer of an absolute risk rule. It cannot improve the ranking or precision at the same recall for strictly increasing transforms.

| Previously specified decision | Actual precision | Actual recall | FP/1,000 |
|---|---:|---:|---:|
| Incumbent >0.2670107781887054 | 34.00% | 56.45% | 222.6 |
| OOF 50% recall rule >0.31280517578124994 | 37.59% | 45.73% | 154.3 |
| OOF 40% recall rule >0.36248219013214106 | 42.20% | 35.17% | 97.9 |
| Fixed >0.5 | 61.73% | 13.07% | 16.5 |

**VERIFIED — row burden and notification burden diverge.** Group flags if and only if consecutive within the same county at exactly 15-minute spacing. The 196,506 flags form 21,958 runs; 9,398 contain a positive row and 12,560 contain none. Similarly, 9,264 of 13,064 contiguous positive-label runs have any flagged row. These are retrospective overlap proxies. A single late flag can count as a hit, separate label runs can share a physical event, and a long flag run can cover multiple targets. For a first-notification policy, implement first-crossing matching and lead time before treating these as event metrics (E4).

The 2021 static cohort confirms geographic and time-of-day heterogeneity. The evidence for geography, clock reliance and alternative explanations is in [geographic generalization](GEOGRAPHIC_GENERALIZATION.md) and [feature audit](FEATURE_AND_MODEL_AUDIT.md). Proposed experiments and acceptance criteria are in [the improvement plan](PRECISION_RECALL_IMPROVEMENT_PLAN.md).

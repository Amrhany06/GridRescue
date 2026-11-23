# Geographic generalization in 2021

The four forests share one training geography. The 12 represented counties supplied 1,053,328 eligible rows from 2018–2020. All years of the four held-out counties and all years of New York's four selected counties stayed outside fitting, preprocessing and CV selection. Their 2021 observations make the two spatial checks. The state result describes the four selected New York counties.

| Evaluation group | Fitting exposure | 2021 rows | Positive prevalence |
|---|---|---:|---:|
| Original three | Previous geographic experiment and expanded fitting | 102,449 | 32.91% |
| Other nine seen counties | Expanded fitting | 262,328 | 20.35% |
| Four unseen counties in seen states | County unseen, state represented | 116,528 | 19.79% |
| Four New York counties | Both county and state unseen | 101,227 | 8.09% |
| **Full expanded evaluation population** | Mix of all four groups | **582,532** | **20.32%** |

The fold-fitted one-hot encoders produce an all-zero block for an unseen category. A new county in a seen state can still use that state's fitted indicator. New York rows get an all-zero state block and FIPS block where present. The resulting scores can differ from the numeric baseline because the geographic forest learned different splits. The encoder prevents an unknown-category error. Transfer quality must be measured on those rows.

2021 was previously reused for experimentation on the original counties. The expanded 2021 comparisons are development evidence. Differences between rows in different evaluations mix geography and class prevalence. Compare variants within a row group, and compare historical models only against the exact original 102,449 rows.

## Results

| 2021 evaluation group | Numeric AP | State AP | FIPS AP | Both AP |
|---|---:|---:|---:|---:|
| Original three | 0.490470 | 0.565505 | **0.569376** | 0.566411 |
| Other nine seen counties | 0.294025 | 0.363826 | 0.367441 | **0.373747** |
| All 12 seen counties | 0.361618 | 0.438562 | 0.446470 | **0.450123** |
| Unseen counties in seen states | 0.297504 | **0.384807** | 0.289785 | 0.381489 |
| Unseen state, New York | 0.124120 | **0.125265** | 0.119639 | 0.117135 |
| Full expanded population | 0.324024 | 0.400952 | 0.394356 | **0.402954** |

**Seen counties.** The combined model led pooled AP across all seen counties and in each chronological CV fold. FIPS-only led the expanded models on the original three counties. All three feature-matched historical comparisons declined on the exact original rows. Across the 20 individual counties, State improved AP over numeric in **17**, FIPS in **10**, and both in **13**. These counts are descriptive, and outcomes can overlap across nearby anchors. [Per-county and per-fold metrics](pilot_20_20261121/model_results/metrics.csv), [paired historical comparison](MODEL_COMPARISON.md#same-row-check-against-the-previous-three-county-models).

**Unseen counties in seen states.** State-only gained **+0.087304 AP (+29.35%)** over numeric, compared with **−0.007719 (−2.59%)** for FIPS and **+0.083985 (+28.23%)** for both. At the fixed threshold, State caught 2,358 of 23,065 positives (10.22% recall), the combined variant caught 438 (1.90% recall), and FIPS predicted zero positives. This is the clearest transfer result for a geographic feature. [Saved scores and confusion matrices](pilot_20_20261121/model_results/metrics.csv).

**Unseen state.** State-only gained **+0.001145 AP (+0.92%)** on the four New York counties. FIPS and both fell by **0.004481** and **0.006985** AP. Every geographic variant predicted zero positives at 0.5, while numeric caught just three of 8,192 positives. The spatial tests do not establish reliable transfer to a new state. This experiment used one held-out state, so its transfer limits are specific to the measured population and period.

## Decision for further development

Keep **State-only as the first geographic candidate for represented-state transfer**, and keep **both as a seen-county and pooled-AP benchmark**. FIPS-only is useful as a seen-county comparison. State produced the best unseen-county ranking and the broadest county gains. Current evidence supports keeping the official frozen model.

The next experiment should prioritize **better past-only historical features on these same geography splits**, before expanding the county count again. For example, test a small, predeclared longer-history ablation with observed coverage flags and robust change summaries. Additional training data in its current form lowered AP on the original matched rows, and all four models missed nearly all positives in the held-out state at the fixed threshold. Keep the numeric reference and repeat held-out-state checks across more than one geographic group if the feature ablation later shows improvement.

[AP plots](pilot_20_20261121/model_results/geographic_comparison.png) · [Comparison and resource details](MODEL_COMPARISON.md)

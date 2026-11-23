# Final recommendation

**Development candidate: XGBoost history, State, cutoff 0.267010778.** It led the four primary State-only variants on mean chronological OOF AP (0.446991). The strongest secondary geography comparison, RF original, State + FIPS, scored 0.467380 in those seen-county folds. The cutoff was selected by maximizing accuracy subject to at least 60% pooled OOF recall. Before deployment, confirm that this recall goal and the corresponding alert load suit the intended workflow.

| 2021 rule | Cutoff | AP | Accuracy | Recall | Precision | F1 | F2 | Balanced acc. | ROC-AUC | False alarms / 1,000 | TN / FP / FN / TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fixed 0.50 | 0.500000 | 0.411168 | 80.69% | 13.07% | 61.73% | 21.57% | 15.52% | 55.50% | 0.700933 | 16.5 | 454,584/9,593/102,884/15,471 |
| Best OOF F2 | 0.116015 | 0.411168 | 36.23% | 92.96% | 23.25% | 37.20% | 58.12% | 57.36% | 0.700933 | 623.4 | 101,046/363,131/8,334/110,021 |
| Accuracy at OOF recall ≥60% | 0.267011 | 0.411168 | 68.89% | 56.45% | 34.00% | 42.44% | 49.86% | 64.25% | 0.700933 | 222.6 | 334,481/129,696/51,545/66,810 |

The candidate’s 2021 AP changed by +0.010216 against the original State forest, on the identical observations. At the proposed cutoff, recall is 56.45% with 222.6 false alarms per 1,000. Keeping cutoff 0.50 on that same candidate yields 13.07% recall and 16.5 false alarms per 1,000.

| 2021 population | Prevalence | AP | Recall | Precision | FP / 1,000 |
| --- | --- | --- | --- | --- | --- |
| All 20 | 20.32% | 0.411168 | 56.45% | 34.00% | 222.6 |
| Original three | 32.91% | 0.577422 | 71.91% | 46.22% | 275.5 |
| Seen (12) | 23.88% | 0.452627 | 58.45% | 38.31% | 224.7 |
| Other seen (9) | 20.35% | 0.372575 | 49.94% | 33.15% | 204.9 |
| Unseen counties (4) | 19.79% | 0.392429 | 54.61% | 31.11% | 239.4 |
| Unseen state, NY (4) | 8.09% | 0.132975 | 40.36% | 14.29% | 195.8 |

The matched-feature XGBoost minus Random Forest mean OOF AP differences were XGBoost original, State +0.003935, XGBoost history, State +0.012160. See [feature comparison](FEATURE_COMPARISON.md) for fold-specific changes from longer history and [model comparison](MODEL_COMPARISON.md) for all fixed and selected cutoffs.

Against the original State forest, the candidate improved AP in 19 of 20 counties. On the unseen New York group, AP increased from 0.125265 to 0.132975, while precision at the proposed cutoff was 14.29%. The candidate still depends heavily on `hour_utc`. Permuting that feature reduced AP by 0.123691 in the diagnostic sample, the largest decrease of any numeric predictor.

Additional development counties remain worth investigating because four unseen-state counties from one state cannot establish nationwide transfer. Before a model freeze, agree on an operational false-alarm budget, evaluate across multiple leave-one-state-out development partitions, and test the candidate’s reliance on `hour_utc` within those partitions. Check whether consolidating consecutive alerts reduces operator load. Any future freeze requires explicit approval. The official model was preserved and 2022 stayed sealed.

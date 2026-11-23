# Feature and model audit

**Verified predictor contract.** The 13 original numeric columns represent the current count, exact 15/60-minute lags, one-hour change, population variance, mean and number of reported slots in the inclusive last hour, three UTC calendar fields and three missingness flags. Eleven extended columns add 120/180-minute lags, 180-minute change and relative change, maximum and coverage over 13 slots, 30-minute slope and four flags. A zero denominator makes relative growth missing. Calendar reconstruction used Spark Sunday=1. Current values may enter windows. Missing slots stay missing until fold-local imputation. See `src/gridrescue/pipeline.py::features` and `reports/modeling/local_improvement/history.py::{history_features,build_bucket}`.

**Verified model identity.** The local pipeline uses 24 numeric plus four fitted state indicator columns. Unknown state is all-zero. FIPS, row labels and future completeness are excluded from the estimator inputs. A CPU histogram booster uses 120 rounds, depth 6, learning rate 0.1, subsample 0.85, two threads, seed 17 and binary logistic loss. Local incumbent SHA-256 matched `local_improvement/model_results/full_fits.json` (353bf2bf9a6a5a43ed38b8fd58c22f56c85fa73be8ee32a27e7830c15ffe0c47). Reloaded `artifacts/modeling/local_improvement/models/xgb_history_state.joblib` and scored every 197th row in each evaluation state partition. All 2,959 scores matched the keyed archive exactly.

## How much does the model add?

**Selection boundary.** Recomputed AP for all 18 new candidate-fold prediction files and reproduced both depth selections. The extended XGBoost mean of 0.446991 leads the four primary state-only variants. Secondary forests using state plus FIPS scored higher in same-county chronological folds (0.467380 original and 0.465507 extended). On the fixed mixed-geography 2021 panel their APs were 0.402954 and 0.403314. This distinction matters if Sol High changes the deployment population: an objective for previously monitored counties can favor a different model from one designed for new counties. Keep these secondary controls in E2.

The following scores use identical 582,532 labels. For the audit's simple lookup baselines, aggregate 2018–2020 seen-county outcomes once. Smooth each cell with 20 pseudo-observations at global training prevalence. An unseen state falls back to training hour prevalence if hour is available, otherwise the global rate. The bins and smoothing were chosen for diagnosis, without a search. No booster refit.

| Ranking score | All 2021 AP | NY AP where computed |
|---|---:|---:|
| Constant prevalence | 0.2032 | 0.0809 |
| UTC hour alone | 0.2661 | 0.0977 |
| State alone | 0.2669 | 0.0809 |
| State × UTC hour | 0.3470 | 0.0977 |
| Hour × severity × sign of 60-minute change | 0.3016 | 0.1103 |
| State × hour × severity × change sign | 0.3694 | 0.0977 |
| RF original / extended history, state | 0.4010 / 0.3949 | |
| XGBoost original / extended history, state | 0.4061 / 0.4112 | |
| Extended XGBoost without hour | 0.3368 | 0.1333 |
| Extended XGBoost with hour | 0.4112 | 0.1330 |

Severity bins use upper edges 50, 200, 400, 1,000 and infinity. Missing change has a separate category. The state × hour lookup alone captures considerable pooled discrimination. The extended XGBoost still earns a 0.0418 AP gain over the richer lookup. Extra history gives +0.00505 AP within XGBoost and a decrease within state-only RF. There is limited evidence for a large gain from further extending these same lag families. Archived in-sample full-fit AP 0.4832, chronological fold AP 0.4370/0.4537/0.4502 and seen-2021 AP 0.4526 do not point to catastrophic optimization failure. Different prevalence and county mix limit comparisons across partitions.

**Hour reliance VERIFIED; mechanism INCONCLUSIVE.** Recomputed paired full and no-hour 2021 AP, delta +0.074402. The delta in NY is −0.00034. The archived county-month permutation test on 20,000 rows also drops AP by 0.123–0.129. Permutation can produce unrealistic feature combinations. The fixed-hyperparameter refit is stronger evidence. Recomputed peak-label / peak-mean-score hours were 21/13 UTC in both Kings and Queens, 15/14 in Los Angeles. LA's archived hourly coverage stays above 99%, yet a scheduled change in *values* could still occur with all slots present. Source timestamps do not distinguish physical cycles, report updates and their mixture.

**Conditional uncertainty.** Paired bootstrap, 300 draws with seed 17. Divide 2021 into successive seven-day blocks from Jan 1 (53rd block is partial), sample 53 blocks with replacement, keep all counties together, apply block multiplicities to exact tied-score AP. Percentile 95% ranges: champion AP 0.4007–0.4207, with-hour minus no-hour +0.0671 to +0.0813, extended minus original XGBoost +0.0028 to +0.0073. These intervals condition on fitted models and this cohort/year. They omit model selection variability, long seasonal dependence and sampling of new states.

**P2 test.** Preserve the current model as control and use the single-factor temporal and cadence comparisons in [the intervention plan](PRECISION_RECALL_IMPROVEMENT_PLAN.md). Reuse identical folds, depth, seed, rows and preprocessing, including a training-only hour/state lookup in every outer fold. Require known score direction, a tested unknown-state fallback, exact future-perturbation invariance and the paired promotion gates. Feature importance alone gives no reason to remove hour.

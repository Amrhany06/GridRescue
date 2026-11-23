# Candidate feature definitions

These are the implemented predictor definitions in `src/gridrescue/pipeline.py`, not model-selected features. Time is interpreted as UTC according to the supplied source documentation. Each row is a unique valid county-time anchor. No future column enters X.

| Predictor | Definition and available information |
|---|---|
| `customers_out_t` | Valid nonnegative integer customer count observed at anchor t. Labels additionally require this count to be positive. |
| `lag_15m` | Same county's count at exactly t−15 minutes; null when absent. |
| `lag_60m` | Same county's count at exactly t−60 minutes; null when absent. Four previous rows are not a substitute. |
| `delta_60m` | `customers_out_t − lag_60m`; null when the exact lag is absent. |
| `rolling_mean_60m` | Mean of observed counts in inclusive [t−60m,t], including the current observation. |
| `rolling_variance_60m` | Population variance over the same observed historical window. One observed value has variance zero. |
| `history_slots_60m` | Number of observed valid unique quarter-hour slots in [t−60m,t], from 1 to 5. No missing row is synthesized. |
| `hour_utc` | UTC hour, 0–23. |
| `weekday_utc` | Spark day-of-week code, Sunday=1 through Saturday=7. Numeric baseline; no cyclical encoding claimed. |
| `month_utc` | UTC month, 1–12. |
| `lag_15m_missing` | 1 if the exact 15-minute lag is absent, otherwise 0. |
| `lag_60m_missing` | 1 if the exact 60-minute lag is absent, otherwise 0. |
| `delta_60m_missing` | 1 if the historical difference is absent, otherwise 0. This duplicates the 60-minute missing flag and is a documented redundant baseline feature. |

The selected vector has 13 numeric predictors. FIPS, county, state, timestamp and epoch remain grouping/audit metadata; no categorical encoding is needed for this numeric-only candidate X. The two history gaps and difference are imputed using medians learned only on eligible 2018–2020 training rows. Every feature must have at least one observed training value. Imputation never creates source observations or fills a missing outcome. Spark StandardScaler learns training mean/sample standard deviation after assembly. Both fitting and saved preparation remain separately subject to execution verification.

`future_slots`, `future_max`, `future_last_epoch`, `future_max_gap_seconds`, `label_complete`, `escalation_threshold`, `candidate_y` and `split` are excluded from X. The provisional label requires 12 future observations in (t,t+3h], a positive current count, and a threshold of current + max(200, 50% of current). Partition-crossing anchors are purged from development preparation. Candidate labels do not authorize predictive training.

No source-zero filling, resampling, interpolation, extreme-count clipping, county-customer denominator, target-driven selection, predictive estimator, or 2022-fitted statistic is part of these definitions.

# Historical feature comparison

Spark 3.5.3 and Hadoop 3.3.4 read the five verified Silver state partitions, found the historical values within each county, and wrote a separate native Parquet dataset. The join retained every eligible anchor and its original label. State-trained comparisons use 1,053,328 training rows in 12 counties and all 582,532 2021 rows in 20 counties. The eight held-out counties were excluded from every fit. Their historical raw reports were used only to calculate their respective evaluation predictors.

| Predictor | Definition |
| --- | --- |
| 120-minute and 180-minute lags | Exact UTC offset. An absent report produces a missing value. |
| Three-hour change | Current outage count minus the exact 180-minute lag. |
| Rolling maximum | Largest observed count in the inclusive [t − 180 minutes, t] window. |
| Reporting coverage | Observed slots divided by 13, including the prediction anchor. |
| Recent trend | Current minus exact 30-minute lag, divided by 30 to represent customers per minute. |
| Relative growth | Three-hour change divided by the exact lag only when that lag is positive. |
| Four missingness flags | Mark unavailable 120-minute lag, 180-minute lag, 30-minute trend, and relative growth. |

| Partition | Eligible rows | 120m lag missing | 180m lag missing | Relative growth missing |
| --- | --- | --- | --- | --- |
| train | 1,053,328 | 30,791 | 38,902 | 38,902 |
| validation | 582,532 | 19,190 | 24,810 | 24,810 |

A Spark range window uses timestamp values, so a missing report does not shift the lag to a neighboring slot. The interval ends at the prediction timestamp. Windows span UTC year boundaries within a county. For a positive current count, the original target requires all twelve future quarter-hour observations and an increase of at least the larger of 200 customers or 50% of the current count. Imputation learns a median per numeric feature in the training partition, and scaling learns that partition’s mean and standard deviation after imputation. Unseen geography produces a zero one-hot block and never gets a learned county or state effect of its own.

## Paired difference in average precision

| History variant versus its original | 2018 H2 Δ | 2019 Δ | 2020 Δ | Mean OOF Δ | 2021 Δ | Relative 2021 Δ |
| --- | --- | --- | --- | --- | --- | --- |
| RF history, State | +0.005669 | +0.000058 | -0.000035 | +0.001897 | -0.006083 | -1.52% |
| RF history, State + FIPS | -0.000396 | -0.001838 | -0.003388 | -0.001874 | +0.000360 | +0.09% |
| XGBoost history, State | +0.011659 | +0.010172 | +0.008538 | +0.010123 | +0.005048 | +1.24% |

Longer history gave XGBoost a positive AP change in every fold and raised its 2021 AP by 0.005049. The Random Forest differences were smaller and mixed. In particular, State-only RF gained 0.001898 mean OOF AP and lost 0.006082 AP in 2021. This experiment supports longer history for the tested XGBoost configuration.

Three temporal folds provide descriptive variation, and consecutive anchors can share an outage event and its future horizon. These paired differences do not establish independent-sample significance. The [model comparison](MODEL_COMPARISON.md) shows group-level results.

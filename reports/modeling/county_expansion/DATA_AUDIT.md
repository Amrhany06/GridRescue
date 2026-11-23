# Expanded development data audit

Spark extracted **2,583,294** records for the frozen 20 counties. Production cleaning retained **2,557,234** unique county-time reports and quarantined **26,060** invalid records. The selected data had zero exact duplicate removals and zero conflicting records after validity checks. The earlier coverage count matches the cleaned count in every selected county. [Machine-readable audit and county-year counts](pilot_20_20261121/data_audit.json).

| Year | Selected raw | Clean | Eligible | Positive eligible |
|---|---:|---:|---:|---:|
| 2018 | 645,866 | 637,492 | 565,360 | 114,224 |
| 2019 | 651,343 | 645,895 | 580,333 | 117,557 |
| 2020 | 639,561 | 630,956 | 562,577 | 117,706 |
| 2021 | 646,524 | 642,891 | 582,532 | 118,355 |
| **Total** | **2,583,294** | **2,557,234** | **2,290,802** | **467,842** |

Every clean report had a positive current customer count. A further **266,432** clean anchors lacked a complete twelve-slot future window and were ineligible. The original three-hour boundary rules were applied. The selected sources contained no rows at the global split cutoffs requiring an additional purge. The chronological CV folds apply their own earlier-label cutoff at each fold boundary. Native Spark writes keep the label audit partitioned by split, with all 13 predictors, metadata and completeness diagnostics.

## Which rows entered fitting

| Frozen geography group | Counties | Eligible 2018–2020 | 2018–2020 rows available for fitting | Eligible 2021 | Positive 2021 |
|---|---:|---:|---:|---:|---:|
| Original three | 3 | 303,791 | 303,791 | 102,449 | 33,719 |
| Other seen counties | 9 | 749,537 | 749,537 | 262,328 | 53,379 |
| Unseen counties in seen states | 4 | 331,856 | 0 | 116,528 | 23,065 |
| Unseen state, New York | 4 | 323,086 | 0 | 101,227 | 8,192 |
| **Total** | **20** | **1,708,270** | **1,053,328** | **582,532** | **118,355** |

The original three counties' training and 2021 keys and labels exactly match the previous run, with numeric features matching at the documented floating-point tolerance (`rtol=1e-12`, `atol=1e-8`). This checks the same-row comparison directly, including the data on which the older forests were fit. The January prefixes are outside the expanded cohort.

## Native Windows processing and resources

- Spark 3.5.3 with verified Hadoop 3.3.4 NativeIO extracted one year at a time. Only selected rows entered the original cleaning, historical lag/rolling feature and label code. Each state was processed separately, with all four years available for its county windows. The full development-source rows were scanned for coverage and selected extraction only.
- Native preparation took **221.6 seconds** after source-hash checks. Yearly extraction took 18.0, 11.3, 23.6 and 22.5 seconds. State processing took 36.7, 28.6, 28.0, 25.7 and 27.2 seconds. Available RAM in Spark stage snapshots varied with the live JVM. The fitted Python working sets are recorded separately in each model run.
- The native Parquet checkpoints use about **90 MiB** for Bronze, Silver, the label audit and quarantine. Workspace free disk went from **1.34 GiB to 1.21 GiB** during preparation. No raw CSV or established artifact was replaced to reclaim space.

The local workspace retains the native preparation log at `prepare_run.log`. [County selection and coverage](COUNTY_SELECTION.md) · [Reproducibility instructions](REPRODUCE.md)

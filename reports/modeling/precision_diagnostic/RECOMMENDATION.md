# Keep XGBoost and test broader geographic transfer

**Decision C. Keep the longer-history, State-encoded XGBoost with `hour_utc` as the experimental champion.** Use the incumbent 60% OOF rule as the recall-focused reference for the next comparison. The existing official model has a separate selection. This diagnostic is development evidence for a future experiment.

| OOF recall target | Frozen cutoff | 2021 recall | Precision | Accuracy | AP | False positives / 1,000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 40% | 0.362482 | 35.17% | 42.20% | 77.04% | 0.411168 | 97.9 |
| 50% | 0.312805 | 45.73% | 37.59% | 73.55% | 0.411168 | 154.3 |
| 60% | 0.267012 | 56.45% | 34.00% | 68.89% | 0.411168 | 222.6 |

The 60% OOF rule had the best OOF F1, F2 and balanced accuracy among these three choices. Its higher recall comes with a substantial false-positive burden. Moving to the 50% rule would reduce that burden by 68.4 false-positive rows per 1,000 in 2021 and lose 10.71 percentage points of recall. The model already provides a modest ranking improvement over Random Forest, including 0.97 points of precision at nearly identical 2021 recall versus the longer-history forest. A threshold change alone did not preserve incumbent recall while improving precision. Removing `hour_utc` reduced AP by 0.074402 in 2021 and weakened ranking in all three chronological folds. [Threshold comparison](PRECISION_RECALL_COMPARISON.md) · [Hour analysis](HOUR_FEATURE_ANALYSIS.md)

## Before scaling up

1. Define the minimum recall and false-positive budget before selecting another cutoff. Decide how consecutive flags for the same county and outage window should be consolidated. Measure whether grouping flags reduces operator workload and whether it delays the first useful flag. The current results measure eligible rows, and overlapping rows can belong to one outage.
2. Plan a bounded development comparison with a broader set of counties across multiple states, time zones, prevalence levels and reporting coverage profiles. Predefine repeated held-out-state evaluations and hold out counties within represented states. Retain purged chronological folds and choose thresholds only on training-period OOF scores. Use the same evaluation rows for each training strategy and publish results by geographic group alongside the pooled AP and precision at a shared recall.
3. Judge expansion by whether it improves ranking or precision at comparable recall on held-out geography, with the false-positive budget and minimum recall checked by group. Retain both hour variants as a controlled comparison where feasible. Check changes with county- or outage-window grouping, since adjacent rows share observations. Keep 2022 sealed until a separately approved final evaluation of a frozen candidate.

Larger, geographically diverse training data are justified as the next experiment. The current result for state transfer comes from one state. New York had 14.29% precision and 40.36% recall at the incumbent cutoff, alongside weaker ranking. California contributed 35.1% of false-positive rows and Pennsylvania had very low recall. More rows drawn mainly from already represented counties would provide little evidence about geographic transfer. Finalize the evaluation design and workload budget locally before using Colab for a larger fit. [Geographic error analysis](GEOGRAPHIC_ERRORS.md)

## Evidence and scope

The diagnostic reused the processed 20-county cohort. It fitted the hour-omitted XGBoost three times for OOF scores and once on the full training split. The independent replay reused those fits with zero training. The cohort, escalation target, protected official artifacts, and Task 1–3 notebooks were preserved. All prediction inputs were from 2018–2021. The run used the prior development data only, and 2021 remains previously consulted development evidence.

[Reproduction steps](REPRODUCE.md) · [Run evidence](results/run_evidence.json) · [Independent verification](verification_extended.json)

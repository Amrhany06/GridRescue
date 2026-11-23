## Current verified state ? 2026-11-17T16:48:43.849687+00:00

Task 1/2 notebooks are ready for personal user review with executed Windows Arrow-local outputs. Native Hadoop writing remains blocked; full tests 40/41 passed with the original native integration error unchanged. See `TASK1_TASK2_CHANGE_SUMMARY.md`, `WINDOWS_SPARK_DIAGNOSIS.md`, `TASK1_TASK2_RUBRIC_REVIEW.md` and `NOTEBOOK_REVIEW_GUIDE.md`. Task 3 remains paused, 2022 sealed for modeling, Linux retained. Older execution statements below are historical and superseded by this verified update.

---

# Label feasibility: measured, unapproved

## Provisional y, exclusions and splits

y=1 when a future reported count in (t,t+3h] reaches current + max(200, 50% of current). Current count must be positive. **Both classes require all 12 exact future quarter-hour slots**. Missing future observations remain unknown, even if a partial future trace contains a threshold crossing. Candidate labels are audit outcomes, not scientific approval.

| Scope | Split | Eligible | Positive | Negative | Unlabelled | Positive share among eligible |
|---|---|---|---|---|---|---|
| Prefix | train | 109,785 | 8,202 | 101,583 | 125,228 | 7.47% |
| Prefix | validation | 53,601 | 4,542 | 49,059 | 45,017 | 8.47% |
| Counties | train | 303,791 | 110,987 | 192,804 | 8,826 | 36.53% |
| Counties | validation | 102,449 | 33,719 | 68,730 | 1,874 | 32.91% |

| Scope | Unlabelled anchors | Complete windows with nonpositive anchor | Boundary-purged anchors |
|---|---|---|---|
| Prefix | 170,245 | 0 | 0 |
| Counties | 10,700 | 0 | 0 |

Training is 2018–2020; validation is 2021. The final 2022 test is sealed and **no test predictor/label rows are materialized**. An absent test row count here means unprocessed, not an empty final-test dataset. Horizon-crossing anchors would be purged; both real scopes have zero such anchors because source years end before the final three hours. Boundary behavior is exercised by the synthetic regression fixture, not a fabricated real example.

## Temporal feasibility and selection

| County / FIPS | Year | Observed days | Clean anchors | Eligible | Positive | Negative |
|---|---|---|---|---|---|---|
| Los Angeles / 06037 | 2018 | 365 | 34,254 | 32,580 | 14,063 | 18,517 |
| Miami-Dade / 12086 | 2018 | 365 | 34,673 | 33,686 | 10,863 | 22,823 |
| Harris / 48201 | 2018 | 365 | 34,644 | 33,535 | 11,209 | 22,326 |
| Los Angeles / 06037 | 2019 | 365 | 34,797 | 34,339 | 15,828 | 18,511 |
| Miami-Dade / 12086 | 2019 | 365 | 34,673 | 32,854 | 9,664 | 23,190 |
| Harris / 48201 | 2019 | 365 | 34,735 | 34,156 | 11,276 | 22,880 |
| Los Angeles / 06037 | 2020 | 366 | 35,011 | 34,773 | 15,799 | 18,974 |
| Miami-Dade / 12086 | 2020 | 366 | 34,925 | 34,047 | 10,338 | 23,709 |
| Harris / 48201 | 2020 | 366 | 34,905 | 33,821 | 11,947 | 21,874 |
| Los Angeles / 06037 | 2021 | 365 | 34,823 | 34,476 | 14,820 | 19,656 |
| Miami-Dade / 12086 | 2021 | 365 | 34,757 | 34,057 | 10,113 | 23,944 |
| Harris / 48201 | 2021 | 365 | 34,743 | 33,916 | 8,786 | 25,130 |

Each selected county has observations on every calendar date in each source year, including 366 dates in 2020; date presence does not imply every quarter-hour is present, and December 31 contains only the source endpoint. Both classes occur in every selected county-year. Eligible prevalence differs greatly from the January prefix subset. Coverage-based complete-case selection and the fixed populous counties can favor sustained, well-reported outages; neither cohort's prevalence generalizes to all counties. Future reporting completeness is unknown at inference time, so retrospective complete-case eligibility is not an operationally available prediction-time selector. Overlapping three-hour anchors are correlated and are not independent outage events.

Actual positive, negative and incomplete traces are in `reports/memory/{sample,county}/label_traces.json`. No real boundary example exists in either scope. Included-versus-all severity and county/state eligibility appear in each audit's `selection_bias` and `coverage_by_county_year` fields. These diagnostics do not justify changing the target or restricting the eventual modeling population without approval.

An independent standard-library check verified 18 exported traces against the exact expected timestamp set, source counts, threshold, maximum and candidate class; see `real_trace_checks.json`. Example: FIPS 01073 at 2018-01-01 00:00 UTC has current count 6, threshold 206, all 12 future slots, future maximum 242, and candidate y=1. Miami-Dade at the same anchor has current 658, threshold 987, future maximum 2,043 and all 12 slots, also candidate y=1.


No predictive training is authorized. Review the strict completeness rule and cohort selection before approving the label.

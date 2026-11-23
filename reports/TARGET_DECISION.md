# Target decision: CONDITIONAL GO

Recommendation only: **approval is still required before training**. The prediction question and numeric threshold are unchanged.

## Exact proposed experiment

- Population: fixed Los Angeles (06037), Miami-Dade (12086), Harris (48201) observations. County-year reporting coverage must meet a predeclared 90% of nominal calendar quarter-hours. 12/12 development county-years meet this criterion, so it removes no development county-years.
- At each reported positive-outage quarter-hour anchor, y=1 if a reported future count reaches current + max(200, 50% of current) within (t,t+3h]. Both classes require all 12 exact future quarter-hours. Incomplete windows remain unknown.
- Training 2018–2020, validation 2021, sealed final test 2022 in the same three predetermined counties. 2022 has not been opened by this audit. No model has been trained.
- The eventual model is a three-county retrospective reported-escalation model, **not nationally representative**, a new-blackout detector, or proof of physical outage absence.

## Actual feasibility evidence

- 418,374 source records; 416,940 clean anchors; 406,240 eligible anchors.
- All 144 county-month-year groups were measured. Minimum positive / negative class counts in a monthly group: **473 / 1,328**.
- County-year reporting coverage ranges **97.76%–99.64%**. Nominal denominators include unreported December 31 slots; source files end at 00:00 that day.
- **99.80%** of eligible anchors have a preceding eligible future window that overlaps. These rows are highly dependent; row count is not independent event count. The three-hour cadence sensitivity is recorded separately, without changing the proposed primary population.
- Monthly/yearly classes, completeness and included-versus-excluded severity are in `target_feasibility.json` and the two eligibility CSVs. Existing 18 independently checked real traces remain in `real_trace_checks.json`.

## Conditions and limitations

Future reporting completeness is unknown at inference time. Strict complete-case labels define a retrospective selected cohort and can favor persistent, well-monitored outages. Coverage qualification is not evidence that missing slots are zero. An approved result must be described conditionally and tested for reporting/severity selection; it cannot be generalized nationally.

Use the same chronological folds for all algorithms, with training label endpoints strictly before validation begins and an embargo of at least three hours. Fit all learned preprocessing only inside each training fold. Reserve 2021 for development validation/model selection. Freeze choices before a single 2022 evaluation. Report overlapping-window dependence and a separate non-overlapping-cadence sensitivity rather than interpreting thousands of adjacent anchors as independent trials.

## Decision requested

Approve or reject the **unchanged three-hour reported-escalation target and this explicit three-county population**. Approval does not authorize a different target, national claims, zero filling, or repeated final-test inspection. Training remains gated until a reply arrives.

# Data expansion and matched evaluation plan

## Frozen populations

Training uses 2018–2020. The same 20 counties supply the same **582,532** eligible 2021 development observations and **118,355** positive labels for all tiers. Tier A reproduces the original **1,053,328** rows from 12 seen counties. All eight original held-out FIPS codes stay excluded from training, and all training FIPS prefixes `36` are rejected to keep the entirety of New York unseen. The original cohort roles and per-county fingerprints are in the reference manifest. [Reference manifest](reference_manifest.json)

## How additional counties enter

1. From 2018–2020 only, count the cleaned quarter-hour reports per county and month using the same exact-duplicate and conflicting-key treatment as the pilot. The approved universe is the 50 states and DC, with New York removed. Existing pilot counties are excluded from the candidate list.
2. Require stable county and State names, observations in all 36 months, minimum 65% coverage in each year, and at least 40% coverage in each month. Use a leap-year-aware denominator. Inside each state, rank by higher minimum annual coverage, then higher minimum monthly coverage, then lexical FIPS. Round-robin across Census regions and states, taking up to 160 candidates. This diversity rule uses report availability and geography. [U.S. Census regions and divisions](https://www.census.gov/programs-surveys/popest/about/glossary/geo-terms.html)
3. Freeze the county order before constructing labels. Once features exist, construct nested whole-county prefixes based on eligible row counts. Eligibility requires a positive current outage and 12 future slots. Positive label values and model metrics play no role in candidate ranking or tier allocation.

| Tier | Training population | Decision gate |
| --- | --- | --- |
| A | Exactly the original 12 training counties | 1,053,328 rows and full trusted hashes |
| B | Tier A plus the eligible county prefix nearest 3,000,000 rows | Accept 2.8–3.2M rows. Leave evidence and stop if coverage is insufficient. |
| C | Longest eligible prefix at or below 8,000,000 rows | Must add rows beyond B and have sufficient runtime capacity. |

Tier B and C counts are unknown until the cloud coverage scan and features run. The notebook reports the actual counts, counties, and states for every tier. Because whole counties are indivisible, Tier C can land below 8M. The manifest discloses how far below. This comparison changes both sample size and geographic breadth. A sample-size-only experiment would need a separate fixed-geography design.

## Evaluation and success criteria

Each tier has expanding OOF validation in July–December 2018, calendar 2019, and calendar 2020. The three-hour label horizon must end strictly before each partition boundary. Freeze highest qualifying cutoffs at 40%, 50%, and 60% pooled OOF recall by keeping equal score blocks together. Use the 60% rule as the main comparison and report actual achieved 2021 recall. The Windows incumbent reference is AP 0.411168, precision 34.00%, recall 56.45%, accuracy 68.89% and 222.6 false-positive rows per 1,000. [Precision diagnostic](../precision_diagnostic/PRECISION_RECALL_COMPARISON.md)

Tier A compares the Cloud scores at the archived incumbent cutoff against Windows before Tier B can begin. The predefined tolerances are 0.002 AP, 1 percentage point for precision, recall, and accuracy, and 10 false-positive rows per 1,000. Row keys and labels must match exactly, separately from model metric parity. Precision at fixed 2021 recall coordinates is descriptive and carries no production cutoff. A result worth pursuing would improve AP or precision at comparable recall, with the performance of the original held-out groups and the false-positive burden visible alongside it. Decide an operational false-positive budget before treating any cutoff as a deployment choice.

The 2021 development cohort includes one completely unseen state. That limits claims about nationwide transfer. Overlapping quarter-hour rows share future observations. Report consecutive flagged runs as potential workload, while requiring independent event identifiers before estimating incident-level precision or recall. [Geographic error analysis](../precision_diagnostic/GEOGRAPHIC_ERRORS.md)

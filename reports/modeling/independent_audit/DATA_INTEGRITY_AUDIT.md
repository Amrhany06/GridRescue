# Data integrity and target audit

**VERIFIED.** The four local development CSVs match the byte lengths and SHA-256 hashes in `reports/modeling/cloud_expansion/source_manifest.json` (Figshare 24237376 v4). This establishes file identity against the pins. Provider accuracy, report latency, changes in utility coverage and physical customer counts require independent evidence.

## Independent reconciliation

Read only the four named CSVs, 2018 through 2021, one year at a time using Arrow string columns. Selected the 20 frozen five-character FIPS, sorted all five source fields and compared every selected record including multiplicity with the corresponding Bronze Parquet. Normalized empty CSV fields and nulls to empty for the comparison. Reparsed the selected records, excluded invalid counts, geography and off-grid times, deduplicated and removed conflicting keys, then compared every surviving record with Silver. All four comparisons at each stage passed. Spark production code uses stricter token validation, UTC parsing and preserves quarantine reasons. The comparison establishes equality for these observed inputs. See `reports/modeling/county_expansion/prepare_cohort.py::{extract_year,prepare_state}` and `src/gridrescue/pipeline.py::{read_source,clean}`.

| Year | Selected raw = Bronze | Silver | Removed |
|---|---:|---:|---:|
| 2018 | 645,866 | 637,492 | 8,374 |
| 2019 | 651,343 | 645,895 | 5,448 |
| 2020 | 639,561 | 630,956 | 8,605 |
| 2021 | 646,524 | 642,891 | 3,633 |

The archived reconciliation attributes all 26,060 removals to invalid rows and records zero duplicate/conflict removals in this cohort. Missing quarter hours are unknown. Forward-filling the source or treating gaps as zero would change both the population and the outcome.

## Independent label and population reconstruction

For each county separately, reindex Silver on a regular UTC 15-minute calendar, leaving gaps missing. Require a positive current value, 12 observed shifts at offsets 1 through 12, and a horizon ending strictly before the next split boundary. Compute the maximum of those 12 readings and compare it with current + max(200, 0.5 × current), including equality. Compare the entire sorted eligible index and every binary label to the archived history partitions for the corresponding role and split. This independently reproduced all 1,053,328 fitted-population rows and 582,532 evaluation rows, including every future-slot count of 12. Seen training counties only. No search across the final holdout boundary. Production implementation in `src/gridrescue/pipeline.py::audit_labels`.

**VERIFIED selection restriction, INCONCLUSIVE direction of bias.** Only 582,532 of 642,891 clean 2021 anchors (90.61%) were scorable under this definition. Of the 60,359 excluded anchors, 5,277 already had at least one observed crossing and 1,543 had no observed future slot. For the latent complete record, counting the other incomplete cases first as all negative then all positive gives a sensitivity range of 123,632–178,714 crossings among 642,891 reports (19.23–27.80%). These are bounds under the assumption that observed values are valid. Missingness alone cannot determine the true prevalence or model performance on those rows. Coverage-based cohort selection also favors consistently observable counties.

**VERIFIED measurement limitation.** A crossing in one recorded slot suffices. Among positive eligible 2021 rows, 24.25% crossed in exactly one slot and 73.94% had at least two consecutive crossings. Persistence can reflect either physical duration or reporting behavior. Several anchors can refer to the same peak. No independent incident ID, utility submission timestamp, service-territory denominator or physical event time appears in the five source fields. Count changes alone cannot identify a storm, additional physical outages, restoration offsetting new outages, batch updates, or a reporting correction.

**P1 coverage intervention.** In a separately versioned evaluator alongside `scripts/audit_target.py`, preserve the denominator of all positive clean anchors. Report complete, incomplete with observed crossing, incomplete without known outcome, zero-future and boundary exclusions by county-month, hour and current-count band. Keep the unchanged primary label. Add fixtures for an absent interior slot, exact-boundary crossing, 200/50% crossover at 400, isolated spikes, explicit zero versus absence, and changing another county. Accept when partitions conserve counts, 2021 reproduces the counts above, no unobserved outcome becomes a negative, and the same-row primary AP remains unchanged. Reporting-only rerun. Testing a persistent target requires separate label version, outcomes and model fits on identical anchors. See [experiment gates](PRECISION_RECALL_IMPROVEMENT_PLAN.md).

# County selection and frozen geographic roles

**20 counties in five states** were frozen before label construction or model fitting. The three original counties are included in the 12 seen counties. Four counties in represented states stay outside all fits, as do all four New York counties.

## Coverage rules

PySpark scanned the four SHA-256-verified 2018–2021 CSVs. The coverage query retained candidate state prefixes and accepted valid, grid-aligned timestamps with consistent geography and nonnegative integral counts. It counted repeated identical source rows once and excluded conflicting county-time records. County and state had to stay consistent across all 48 months. The denominator is 96 possible reports per day, including leap day in 2020. Escalation labels, prevalence and model scores played no role.

Within each state, qualifying counties were ordered by their lowest annual coverage, with ascending FIPS to break ties. The original three were retained. The preferred additional states were Illinois and New York, with Pennsylvania, Ohio, North Carolina and Washington as reserves. The initial 90% annual and 80% monthly floors were too restrictive. The strictest feasible common tier was **65% in every year and 40% in every month**, after testing 75% and 50% together. Pennsylvania replaced Illinois, which had one qualified county at this tier. The realized lowest annual and monthly rates among selected counties were 72.54% and 42.29%, both in Riverside. The expanded cohort therefore includes more uneven reporting than the original three-county cohort.

The state holdout was reserved for the fifth state, New York. In each of the four represented states the non-original county with the lowest SHA-256 of `17:<FIPS>` was held out. The other three counties in each state were eligible to train. [Frozen selection and counts at each coverage tier](pilot_20_20261121/cohort.json).

| County | FIPS | State | Role | Worst year | Worst month | Clean reports, 2018–2021 |
|---|---|---|---|---:|---:|---:|
| Los Angeles | `06037` | California | Seen, original | 97.76% | 95.03% | 138,885 |
| San Diego | `06073` | California | Seen | 85.32% | 64.58% | 124,337 |
| San Bernardino | `06071` | California | Unseen county | 74.67% | 44.55% | 118,978 |
| Riverside | `06065` | California | Seen | 72.54% | 42.29% | 119,426 |
| Miami-Dade | `12086` | Florida | Seen, original | 98.95% | 95.83% | 139,028 |
| Broward | `12011` | Florida | Seen | 98.60% | 95.16% | 138,505 |
| Palm Beach | `12099` | Florida | Unseen county | 96.41% | 91.87% | 135,465 |
| Pinellas | `12103` | Florida | Seen | 87.40% | 66.97% | 125,633 |
| Harris | `48201` | Texas | Seen, original | 98.87% | 94.29% | 139,027 |
| Tarrant | `48439` | Texas | Unseen county | 95.88% | 82.69% | 135,107 |
| Dallas | `48113` | Texas | Seen | 95.25% | 78.92% | 135,732 |
| Montgomery | `48339` | Texas | Seen | 82.00% | 69.02% | 119,396 |
| Philadelphia | `42101` | Pennsylvania | Seen | 95.13% | 59.91% | 137,523 |
| Montgomery | `42091` | Pennsylvania | Seen | 81.44% | 57.19% | 123,134 |
| Bucks | `42017` | Pennsylvania | Unseen county | 79.01% | 58.84% | 116,403 |
| Chester | `42029` | Pennsylvania | Seen | 75.64% | 50.74% | 114,938 |
| Kings | `36047` | New York | Unseen state | 86.41% | 69.42% | 128,305 |
| Queens | `36081` | New York | Unseen state | 86.38% | 75.84% | 127,039 |
| Suffolk | `36103` | New York | Unseen state | 85.95% | 71.98% | 123,673 |
| Nassau | `36059` | New York | Unseen state | 79.83% | 54.17% | 116,700 |

The first 2021 coverage query ran out of workspace disk space while spilling shuffle data. The completed 2018–2020 checkpoints were retained, and 2021 completed in a fresh Spark process. Total times of the four completed queries were 40.4, 35.8, 37.9 and 87.3 seconds. The local workspace retains `coverage_resume.log`. [Reproduce the run](REPRODUCE.md)

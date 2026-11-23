# Official Task 1/2 rubric — executed evidence

Source: the original three-page Task 1/2 PDFs in docs/requirements. PASS is scoped to the displayed real-data populations and verified Arrow-local persistence; it does not assert native Hadoop repair, national Gold processing, or completion of Task 3.

| Task | Original requirement | Status | Notebook evidence |
|---|---|---|---|
| task1_eda | Read Data | PASS | `task1_eda-003`; executed cell 2 |
| task1_eda | Random Sample Data | PASS | `task1_eda-005`; executed cell 3 |
| task1_eda | Size of Data | PASS | `task1_eda-007`; executed cell 4 |
| task1_eda | Information: types, non-null counts, memory | PASS | `task1_eda-009`; executed cell 6 |
| task1_eda | Column names | PASS | `task1_eda-011`; executed cell 7 |
| task1_eda | Descriptive statistics | PASS | `task1_eda-013`; executed cell 8 |
| task1_eda | Unique values | PASS | `task1_eda-015`; executed cell 9 |
| task1_eda | Candidate class balance | PASS | `task1_eda-017`; executed cell 10 |
| task1_eda | Missing values and absent rows | PASS | `task1_eda-019`; executed cell 11 |
| task1_eda | Duplicates and conflict reconciliation | PASS | `task1_eda-021`; executed cell 13 |
| task1_eda | Outlier detection | PASS | `task1_eda-023`; executed cell 15 |
| task1_eda | Outlier treatment comparison | PASS | `task1_eda-025`; executed cell 16 |
| task1_eda | Univariate analysis | PASS | `task1_eda-027`; executed cell 17 |
| task1_eda | Feature versus provisional target | PASS | `task1_eda-029`; executed cell 18 |
| task1_eda | Feature-to-feature analysis | PASS | `task1_eda-031`; executed cell 19 |
| task1_eda | Correlation analysis | PASS | `task1_eda-033`; executed cell 20 |
| task1_eda | Grouped statistical summaries | PASS | `task1_eda-035`; executed cell 21 |
| task1_eda | Written observations and concise findings | PASS | `task1_eda-037`; executed cell 23 |
| task2_preprocessing | Feature list, types, identifiers and exclusions | PASS | `task2_preprocessing-003`; executed cell 2 |
| task2_preprocessing | Create safe features | PASS | `task2_preprocessing-005`; executed cell 4 |
| task2_preprocessing | Review changes and exact-time lag check | PASS | `task2_preprocessing-007`; executed cell 5 |
| task2_preprocessing | X and candidate y definitions | PASS | `task2_preprocessing-009`; executed cell 7 |
| task2_preprocessing | Chronological split and sealed test design | PASS | `task2_preprocessing-014`; executed cell 11 |
| task2_preprocessing | Leakage prevention | PASS | `task2_preprocessing-014`; executed cell 11 |
| task2_preprocessing | Training-only missing-value handling | PASS | `task2_preprocessing-017`; executed cell 12 |
| task2_preprocessing | Categorical encoding decision | PASS | `task2_preprocessing-003`; executed cell 2 |
| task2_preprocessing | Training-only scaling | PASS | `task2_preprocessing-017`; executed cell 12 |
| task2_preprocessing | Processed shape and examples | PASS | `task2_preprocessing-019`; executed cell 15 |
| task2_preprocessing | Feature validation and consistent dimensions | PASS | `task2_preprocessing-021`; executed cell 16 |
| task2_preprocessing | Save and reload preparation | PASS | `task2_preprocessing-023`; executed cell 17 |

Task 1 submission checklist: required sections/subsections, executable outputs/plots, observations, cleaning/treatment reasons, and concise findings are present. Task 2 stops before model selection/training. Complete Spark preprocessing is fitted/reloaded; native Hadoop writing remains a separately reported failed integration.

Additional required evidence: scope ledger, invalid-row examples and cleaning impact; manual full-year county lag/window example; thirteen-feature definitions; nested eligibility stages; real imputation/scaling example; saved 13-position vectors; fresh-process reload parity. See NOTEBOOK_REVIEW_GUIDE.md for exact IDs.

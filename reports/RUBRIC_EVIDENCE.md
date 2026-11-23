# Requirement-to-evidence matrix

Original ML PDFs were read directly from `docs/requirements/` (five pages). Big Data requirements below come from the user’s final implementation plan. PASS means the named scoped item has evidence, not that the entire project is complete. Team membership (5–7 students) remains the team’s responsibility.

| Area | Official item | Status | Evidence / notebook cell | Limitation |
|---|---|---|---|---|
| task1_eda | Read Data | PASS | notebooks/task1_eda.ipynb cell `task1_eda-003` (execution 2) |  |
| task1_eda | Random Sample Data | PASS | notebooks/task1_eda.ipynb cell `task1_eda-005` (execution 3) |  |
| task1_eda | Size of Data | PASS | notebooks/task1_eda.ipynb cell `task1_eda-007` (execution 4) |  |
| task1_eda | Information: types, non-null counts, memory | FAIL | notebooks/task1_eda.ipynb cell `task1_eda-009` (execution 5) | Allocated Spark cache, Python RSS and bounded pandas memory are distinct measurements. |
| task1_eda | Column names | PASS | notebooks/task1_eda.ipynb cell `task1_eda-011` (execution 6) |  |
| task1_eda | Descriptive statistics | PASS | notebooks/task1_eda.ipynb cell `task1_eda-013` (execution 7) |  |
| task1_eda | Unique values | PASS | notebooks/task1_eda.ipynb cell `task1_eda-015` (execution 8) |  |
| task1_eda | Candidate class balance | PASS | notebooks/task1_eda.ipynb cell `task1_eda-017` (execution 9) | Candidate y remains unapproved; cohort-specific evidence. |
| task1_eda | Missing values and absent rows | PASS | notebooks/task1_eda.ipynb cell `task1_eda-019` (execution 10) |  |
| task1_eda | Duplicates and conflict reconciliation | PASS | notebooks/task1_eda.ipynb cell `task1_eda-021` (execution 11) |  |
| task1_eda | Outlier detection | PASS | notebooks/task1_eda.ipynb cell `task1_eda-023` (execution 12) |  |
| task1_eda | Outlier treatment comparison | PASS | notebooks/task1_eda.ipynb cell `task1_eda-025` (execution 13) |  |
| task1_eda | Univariate analysis | PASS | notebooks/task1_eda.ipynb cell `task1_eda-027` (execution 14) |  |
| task1_eda | Feature versus provisional target | PASS | notebooks/task1_eda.ipynb cell `task1_eda-029` (execution 15) | Candidate y remains unapproved; cohort-specific evidence. |
| task1_eda | Feature-to-feature analysis | PASS | notebooks/task1_eda.ipynb cell `task1_eda-031` (execution 16) |  |
| task1_eda | Correlation analysis | PASS | notebooks/task1_eda.ipynb cell `task1_eda-033` (execution 17) |  |
| task1_eda | Grouped statistical summaries | PASS | notebooks/task1_eda.ipynb cell `task1_eda-035` (execution 18) |  |
| task1_eda | Written observations and concise findings | PASS | notebooks/task1_eda.ipynb cell `task1_eda-037` (execution 19) |  |
| task2_preprocessing | Feature list, types, identifiers and exclusions | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-003` (execution 2) |  |
| task2_preprocessing | Create safe features | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-005` (execution 3) |  |
| task2_preprocessing | Review changes and exact-time lag check | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-007` (execution 4) |  |
| task2_preprocessing | X and candidate y definitions | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-009` (execution 5) |  |
| task2_preprocessing | Chronological split and sealed test design | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-014` (execution 8) |  |
| task2_preprocessing | Leakage prevention | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-014` (execution 8) |  |
| task2_preprocessing | Training-only missing-value handling | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-017` (execution 9) |  |
| task2_preprocessing | Categorical encoding decision | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-003` (execution 2) |  |
| task2_preprocessing | Training-only scaling | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-017` (execution 9) |  |
| task2_preprocessing | Processed shape and examples | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-019` (execution 10) |  |
| task2_preprocessing | Feature validation and consistent dimensions | PASS | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-021` (execution 11) |  |
| task2_preprocessing | Save and reload preparation | FAIL | notebooks/task2_preprocessing.ipynb cell `task2_preprocessing-023` (execution 12) | Blocked until real persisted processed data and fitted preparation reload successfully. |
| Task 3 | Problem and research summary | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Three preprocessing/model pipelines | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Default baselines first | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Identical chronological CV and embargo | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Fold metrics mean and standard deviation | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Bounded development-only tuning | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Default-versus-tuned comparison | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Classification diagnostics | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Development-only winner selection | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Once-only 2022 evaluation | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Task 3 | Complete model save and fresh-process reload | FAIL | notebooks/task3_modeling.ipynb; no predictive execution evidence | Scientific target approval required before training; no scores invented. |
| Big Data | Documented collection/source | PASS | reports/source_manifest.json |  |
| Big Data | Cleaning/preparation | PASS | reports/memory/county/audit.json |  |
| Big Data | Real PySpark transforms, aggregates, joins and time windows | PASS | notebooks/task2_preprocessing.ipynb |  |
| Big Data | EDA with actual plots and interpretations | PASS | notebooks/task1_eda.ipynb |  |
| Big Data | Project-specific analysis | FAIL | reports/TARGET_DECISION.md |  |
| Big Data | Interactive dashboard: source, title, KPIs, charts, filters, findings | FAIL | reports/dashboard_verification.json | No model results available until Task 3 is approved and executed. |
| Big Data | Meaningful measured performance comparison | FAIL | reports/performance_comparison.json |  |
| Big Data | Concise report | PASS | reports/FINAL_REPORT.md |  |
| Big Data | Demo/presentation plan | FAIL | docs/DEMO_PLAN.md |  |
| Big Data | README setup and reproduction | PASS | README.md |  |

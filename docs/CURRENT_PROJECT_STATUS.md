# GridRescue current project status

Post-audit handoff, 23 November 2026. This records the state before GitHub publication. See the [technical project report](PROJECT_TECHNICAL_REPORT.md) for the review snapshot and the [Antigravity handoff](ANTIGRAVITY_HANDOFF.md) for local reproduction steps.

| Status | Work |
|---|---|
| Completed | No-fit evaluation of both archived score series on 582,532 fixed 2021 development rows. Replayed each model's three purged OOF folds on 890,035 rows and recovered the archived cutoffs. Added provenance, 32 geography and population slices, 55%/60% matched-recall coordinates, frozen-policy decisions, paired 7-/14-day intervals, and flag-run workload. |
| Completed | Local fold resume now binds score files to ordered predictor and label content, fold membership, estimator settings, source code and runtime versions. Legacy unbound caches remain read-only evidence. |
| Completed | Colab notebook bundle rebuilt and verified locally. Tier A checks exact cohort and fold identities, predictor values and null masks on 262 full-checkpoint anchors, fitted preprocessing on 147 anchors, and same-runtime reload and fixed-cutoff metric parity. |
| Completed | Official university notebooks and frozen Random Forest evidence preserved. Local verification checked eight protected official files and four experimental model binaries. |
| Completed | Native Spark persistence works in the Windows process with the existing pinned Hadoop binaries. Development fixtures exercised exact frozen predictions and synthetic audit/quarantine writes. |
| Partial | Tier A is prepared for the first authorized Colab/Linux run. Actual end-to-end Linux parity, Drive restore, quota and peak resources remain unverified. |
| Partial | Official development notebooks and the historical Streamlit dashboard exist. The working inference form, presentation of score explanations, final course reports/demo and team roster remain. |
| Blocked by owner approval | Sealed final evaluation, Tier A execution with data transfer, and any later expansion. |
| Pending | Phase C was deferred. Weak ranking, geographic transfer, small-outage misses, the cause of UTC-hour dependence and incomplete reporting outcomes remain research questions. The phase produced no new model or improvement claim. |
| Not started | Prospectively selected multi-state outer validation, one-to-one timed crossing notification evaluation and physical incident linkage, Tier B/C, and a deployed inference application. |

## Verified benchmark

The official model remains the original three-county Random Forest with fixed cutoff 0.5. The experimental champion remains depth-6 CPU XGBoost with extended history, state, and UTC hour. The replay reproduced AP **0.4111679018**, precision **33.99896%**, recall **56.44882%**, accuracy **68.88737%**, and **222.64185 FP rows per 1,000**. Confusion counts were TP **66,810**, FP **129,696**, TN **334,481**, FN **51,545**. The incumbent cutoff **0.2670107781887054** came from earlier OOF data. 2021 has been repeatedly consulted and serves as development data.

At the incumbent cutoff, 196,506 flagged rows form 21,958 county flag runs, of which 12,560 contain only negative labels. Exposure was 7,257 eligible county-days and 145,633 eligible row-hours. These are workload counts. At a descriptive 60% recall, precision was 37.87% in seen counties, 29.65% in unseen counties in represented states and 12.24% in unseen New York. The full champion/no-hour comparison used 2,000 usable draws for each block length. The paired AP difference had a 95% interval of [0.0670, 0.0815] for seven-day blocks and [0.0663, 0.0828] for fourteen-day blocks on this archived development cohort.

## Verification in this handoff

| Command or check | Outcome |
|---|---|
| `python -m unittest discover -s tests -v` | 51 run, 50 passed, one error in `test_preparation_fits_only_training_and_saves_reload` with `HADOOP_HOME` unset. |
| Native persistence test, rerun with the existing checksum-verified Hadoop binaries | 1 passed. Set `HADOOP_HOME` and place its `bin` first on PATH in the current process. |
| `scripts/preflight.py` native and development fixture functions in temporary scratch | Verified Python worker, native Parquet write/read/overwrite, Spark pipeline save/reload, 100 exact frozen model scores, 15 synthetic label-audit rows and one quarantine row. |
| `python -m unittest discover -s reports/modeling/local_improvement -v` | 12 passed. |
| `python -m unittest discover -s reports/modeling/precision_diagnostic -v` | 7 passed. |
| `python -m unittest discover -s reports/modeling/cloud_expansion -v` | 16 passed, including 3 small local Spark fixtures. |
| `python -m pip check` and `python -m compileall -q src scripts tests reports/modeling/local_improvement reports/modeling/precision_diagnostic reports/modeling/cloud_expansion` | Both exited 0. |
| Archive replay | 582,532 rows, 32 slices, exact confusion counts and cutoff, five metrics reproduced, 2,000 paired draws at each block length. Evidence in local `artifacts/post_audit_evaluation.json`. |
| Colab preparation verifier | 13 code cells compiled, 7 disabled-action defaults verified, 23 embedded files matched, 6 fold partitions matched, 890,035 OOF rows checked, 82 fixture rows and 262 parity feature rows checked, 147 saved predictions reloaded exactly. Evidence in local `artifacts/post_audit_colab_verification.json`. |
| Final artifact review | 21 replay input hashes and both handoff files' relative links verified. Replayed the 147 serialized Tier A preprocessing vectors and scores with the saved XGBoost model. |

Spark and Streamlit emitted runtime warnings during local tests. The held-out 2022 data, Colab, nationwide feature construction and large model training were outside this work.

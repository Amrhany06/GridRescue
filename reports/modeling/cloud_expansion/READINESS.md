# Cloud-first preparation readiness

The experiment is ready to start with the notebook’s small Colab checks. The four 2018–2021 EAGLE-I inputs are pinned to Figshare article 24237376 v4, and the existing Windows CSVs match both checksum sets. The cloud runtime can obtain **4.11 GiB** directly from Figshare. The notebook uses approximately **123 KiB** for the code, manifests and equivalence sample. [Data source audit](DATA_SOURCE_AUDIT.md)

**Start with cells 1–5** in the [Colab notebook](../../../notebooks/colab_gridrescue_large_scale.ipynb). Inspect the runtime, install the isolated dependencies, mount Drive, inspect the source metadata, then run the sample match. The large stages are disabled on delivery. [Detailed setup and recovery](COLAB_USER_GUIDE.md)

## Measured and estimated capacity

| Item | Capacity |
| --- | ---: |
| Free Windows disk at inventory | 35,391,336,448 bytes (32.96 GiB) |
| Existing pilot Silver Parquet | 36,035,218 bytes |
| Existing eligible history Parquet | 49,457,933 bytes |
| Expected eligible Parquet, Tier B plus fixed 2021 | About 108 MB |
| Expected eligible Parquet, Tier C plus fixed 2021 | About 259 MB |
| Suggested cloud persistence and scratch | 10 GiB Drive free and 22 GiB VM scratch free |
| Typical planning RAM for Tier B / near-8M Tier C | 10–12 / 24–32 GiB available |

## What passed in Windows preparation

- Four local source files matched the Figshare v4 sizes and MD5s and the trusted SHA-256 values.
- Spark matched 82 trusted observations across 20 counties on all 24 predictors, keys, labels, and future-slot counts. A future-only spike flipped a test label while its historical features stayed the same.
- All six archived fold partitions matched the cloud reader’s exact keys and labels. All three cutoffs matched the previous diagnostic when recomputed using 890,035 saved OOF scores.
- The notebook code cells compiled and each of the seven optional action cells ran its safe default branch. All embedded files matched the reviewed workspace sources.
- Eight protected official files and four saved experimental models matched their recorded digests. The 2022 file remained sealed. The preparation did not run a nationwide transfer, a nationwide feature build, or an XGBoost fit.
- The 14 cloud-focused tests and 46 existing repository tests passed. Both Windows Spark suites exited with code 0 after emitting launcher and cleanup diagnostics.

## Checks that happen in Colab

The dependency install and Spark sample test still need their first run on Colab Linux. Before any fit, the notebook verifies the full reconstructed Tier A and 2021 identities and labels against Windows. Tier A then verifies metric parity at the incumbent cutoff before expansion. The actual sizes of Tiers B and C depend on historical coverage and eligibility. Runtime limits can stop the largest fit. The fixed 2021 cohort still has only one unseen state, and changing the training counties changes both volume and geographic breadth.

## Files

- [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md), [DATA_SOURCE_AUDIT.md](DATA_SOURCE_AUDIT.md), [DATA_EXPANSION_PLAN.md](DATA_EXPANSION_PLAN.md), and [COLAB_USER_GUIDE.md](COLAB_USER_GUIDE.md)
- [Cloud runner](cloud_run.py), [Source and checkpoints](cloud_core.py), [Spark data stages](cloud_data.py), and [Training and reporting](cloud_train.py)
- [Source pins](source_manifest.json), [Experiment contract](experiment_manifest.json), [Reference hashes and geography](reference_manifest.json), and [Storage evidence](local_storage_audit.json)
- [Notebook builder](build_notebook.py), [Fixture and inventory generator](prepare_local.py), [Focused tests](test_cloud.py), [Spark tests](test_cloud_spark.py), and [Independent verification](preparation_verification.json)

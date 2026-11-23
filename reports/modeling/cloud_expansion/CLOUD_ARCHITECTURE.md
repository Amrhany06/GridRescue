# Cloud architecture

The notebook transfers the four Figshare CSVs directly to Google Drive from Colab. Colab copies verified inputs to VM scratch for Spark reads and model fitting. Drive holds the durable source objects and checkpoint archives. The notebook embeds its Python code, manifests, and small fixture. The Windows upload is the notebook itself.

## Execution order

| Stage | Input | Check before the next stage |
| --- | --- | --- |
| Inspect source and run the fixture | Figshare v4 metadata and bundled Bronze sample | Provider IDs, sizes, and MD5s match. All 24 predictors and the exact keys and labels match on 82 trusted observations. |
| Stream source files | Four verified metadata entries | Each file has the pinned byte count, provider MD5, and trusted SHA-256. |
| Reconstruct the pilot | The four verified CSVs | Overall and per-county row-and-label fingerprints match Tier A and 2021. Sampled predictor values also match the Windows outputs. |
| Fit and score Tier A | The original 12 training counties | Three frozen OOF cutoffs, a reloaded model, the identical 2021 evaluation population, and a benchmark parity check. |
| Plan and prepare expansion | Coverage from 2018–2020 only | Frozen candidate order, reconciled counts, geographic exclusions, and actual tier sizes. |
| Fit and score Tier B and optional Tier C | The corresponding nested training tier | Locked OOF cutoffs before opening evaluation scores. One fixed pipeline and the same development population per tier. |

## Processing and training

Spark 3.5.3 reuses the same CSV reader, cleaning, labels, and historical feature functions used on Windows. Its UTC parser keeps identifiers as strings and removes conflicting county-time keys. Window functions use epoch seconds, with exact past lags and explicit missing values. The three-hour future window supplies only labels and audit fields. The train and development partitions, and all chronological fold boundaries, use a strict three-hour purge. The original 24 numeric columns and fold-fitted State one-hot encoding feed the classifier. The median imputer and standard scaler learn from each fit partition.

Coverage is reduced to county-month counts one year at a time. Raw Bronze writes are filtered to the pilot or frozen shortlist and partitioned by State FIPS prefix. Feature construction handles at most 12 counties per expanded state batch. Spark uses local shuffle space. Arrow pushes county and timestamp filters into Parquet reads, and the trainer releases each fit frame before reading its OOF observations. Training uses the archived two-thread, depth-6, 120-round CPU histogram XGBoost. The run records peak fit RSS and guards each fit using the selected row count and estimated encoded width. Raw multi-year CSVs never become a pandas frame. [Experiment manifest](experiment_manifest.json)

Keeping Spark avoids a second implementation of subtle parser, duplicate, population-variance, and missing-slot behavior. The largest dense fit may exceed Colab's assigned memory. In that case the code stops at its resource gate. Resume on a higher-memory compatible runtime or keep Tier B as the largest result. External-memory XGBoost is a possible separately validated route if a larger runtime is unavailable. It would need to preserve the training-fitted preprocessing and re-pass Tier A. [XGBoost external-memory documentation](https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/external_memory.html)

## Persistence and integrity

The run name binds the source pins, code and reference file hashes, package versions, CPU device, Python minor version, and Java major version. Each completed stage publishes an archive with SHA-256 plus a manifest of its file hashes. On reconnect, the same notebook and compatible runtime restore the published archive instead of rebuilding it. An interrupted stage with no published archive resumes from the most recent completed boundary. The raw stage can resume byte ranges within a file. Use one active notebook runtime for a given Drive folder.

Full model and threshold files stay in cloud checkpoints. For evaluation, the notebook applies frozen cutoffs and emits AP, recall, precision, accuracy, balanced accuracy, F1, F2, false-positive rate, and false-positive rows per 1,000. The report includes overall, seen, unseen-county, unseen-state, and individual-county slices. It also exports descriptive precision at fixed actual recall coordinates and consecutive flag-run counts as a workload proxy. [Colab user guide](COLAB_USER_GUIDE.md)

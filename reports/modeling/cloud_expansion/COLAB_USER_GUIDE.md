# Run GridRescue in Colab

Open [colab_gridrescue_large_scale.ipynb](../../../notebooks/colab_gridrescue_large_scale.ipynb) in [Google Colab](https://colab.research.google.com/) with **File → Upload notebook**. The notebook includes the code and the compact fixture. Start with Python 3.12 on a CPU runtime. Leave each expensive-stage switch set to `False` during the first checks.

## First cells to run

1. **Inspect this runtime** prints CPU, Python, memory, scratch disk and any GPU.
2. **Unpack the bundled code and install the pinned dependencies** verifies the embedded ZIP, then installs into an isolated VM environment. If prompted about Java, set `INSTALL_JAVA17 = True` and rerun cell 2. The published XGBoost CPU wheel covers x86-64 Linux. [XGBoost CPU package](https://pypi.org/project/xgboost-cpu/3.2.0/)
3. **Mount Google Drive and choose a persistent folder** uses `/content/drive/MyDrive/GridRescueCloud`. Confirm at least 10 GiB of free Drive quota and use the same folder on reconnect. Aim for 22 GiB of free VM scratch. The pilot enforces a 15 GiB scratch and 7 GiB available RAM floor, and each fit checks its expected memory separately.
4. **Inspect the Figshare source** requests small public metadata and displays the four pinned assets.
5. **Reproduce a trusted sample** reconstructs 82 sampled observations and checks their keys, labels, and all 24 inputs. Wait for this to pass before starting large work.

After the owner authorizes a Tier A run, set `RUN_DOWNLOAD = True` in cell 6. After the four files verify, run cell 7 with `RUN_PILOT = True`. Require exact whole-cohort and per-county keys and labels plus the stratified 115-train and 147-development feature panel, including null masks. Enable `RUN_TIER_A` in cell 8 after these gates pass. Require exact purged fold memberships, OOF-only threshold selection, preprocessing panel parity, same-runtime model reload, and overall Windows metric tolerances at the incumbent cutoff. Review the reported state and score deviations. The first authorized run stops at Tier A. [Storage and memory estimates](DATA_SOURCE_AUDIT.md)

Verify one completed checkpoint from fresh scratch before requesting approval to expand. Tier B and C change county breadth and row volume together. After separate approval, use cell 9 to prepare expansion and inspect the actual counts before enabling either fit.

## Recover progress and retrieve results

After a disconnect, open the same notebook, run cells 1–5 again, and rerun the last active stage. The run name reuses compatible checkpoints. Cell 13 lists published checkpoint archives. Each completed stage verifies its archive and content hashes before use. If a `.partial` CSV remains, rerun the download cell to request the remaining bytes. A completed file with the wrong checksum requires inspection and moving the named file aside before retrying. Keep one active runtime per Drive folder. If RAM or scratch is insufficient, switch to a larger compatible runtime or retain the last completed tier.

Set `EXPORT_TIERS = ['A', 'B']` in cell 12 after both tiers finish. Include `'C'` only after C is evaluated. In Drive the notebook prints the exact location of `comparison-A-B.zip`, with `comparison.csv`, the report breakdowns, and `precision_recall.png`. `tier-A-final.zip` and the corresponding B and C artifacts contain `pipeline.joblib`, `booster.ubj`, and fit evidence. Keep `tier-*-thresholds.zip` beside the model to reproduce its operating cutoff. The report archive can be downloaded to Windows without copying the training data back.

## Rebuild the notebook locally

From the GridRescue root, run the following with the existing Windows environment. The preparation script reads known development artifacts and streams local checksum verification. It performs no cloud download or fit.

```powershell
$py = '.\.venv\Scripts\python.exe'
$cloud = 'reports/modeling/cloud_expansion'
& $py "$cloud/prepare_local.py" --tier-a-parity-only --output artifacts/colab_reference_check
& $py "$cloud/build_notebook.py"
& $py "$cloud/verify_preparation.py"
& $py "$cloud/test_cloud.py" -v
& $py scripts/configure_windows_native_spark.py -- $py "$cloud/test_cloud_spark.py" -v
```

The bundled command line runner exposes the same stages for a compatible Linux runtime. `python cloud_run.py --help` lists arguments. The four heavy phases require explicit `--execute`. The official notebooks and model artifacts are separate from all cloud outputs.

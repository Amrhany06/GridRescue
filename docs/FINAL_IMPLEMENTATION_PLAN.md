# GridRescue completion plan

## Preserved baseline

Checkpoint: `artifacts/checkpoints/20261116T235955/verified-project.zip`.
SHA-256: `1EE05A40E79A349FE50EC2E131A500CA59E27583AEB2922095E2196C150F9B64`.
Includes current notebooks, implementation, tests, reports, documentation and configuration. Original CSVs stay unchanged in `data/raw/`.

## Ordered milestones and acceptance

1. **Phase 0:** read original PDFs; generate a cell-level evidence matrix, verify checkpoint and existing saved outputs. Use the user's supplied Big Data requirements; team membership remains outside automated verification.
2. **Phase 1:** keep the working 19-cell Task 1 and Windows memory fallback; quantify memory with explicitly scoped measurements. Prepare Linux setup and run real Parquet, processed-data and preprocessing reload checks after runtime approval. Preserve fallback notebook outputs and keep Linux execution evidence separate.
3. **Phase 2:** audit fixed counties by county/month/year, reporting coverage, strict 12-slot eligibility, classes, severity selection, examples and overlap. Propose the unchanged target for a retrospective three-county experiment with explicit coverage qualification. Ask for scientific approval using measured evidence; do not train before it.
4. **Phase 3 (gated):** default LR/RF/HGB pipelines, common purged chronological folds (>=3-hour embargo), fold-fitted preprocessing, bounded training-only tuning, 2021 validation selection, one frozen 2022 evaluation, whole-pipeline fresh-process reload. No scores or PASS claims before execution.
5. **Phase 4 (independent):** retain Streamlit, repair its data connection to verified exports, add scope/KPI/insight provenance and test real state/county/date/severity interactions, reconciliation and server launch. No live-monitoring claim or invented model panel.
6. **Phase 5:** rerun relevant notebooks/checks, produce acceptance ledger, concise report, README, demo/presentation outline and beginner discussion guide. PASS requires actual evidence. Blocked requirements remain FAIL with an explanation.

No major rewrite, third-party Hadoop binary installation, raw-data changes, model training before target approval, production deployment or automatic restart is authorized.

## Proposed persistence environment (approval required)

Read-only probes confirm WSL is not installed. Docker and Podman are not available in PATH. Prefer official Microsoft WSL 2 plus **Ubuntu 24.04 LTS**, keeping the existing Windows `.venv` unchanged.

Windows command to be approved:

```powershell
wsl.exe --install --distribution Ubuntu-24.04 --no-launch
```

This installs an official WSL runtime/distribution and may enable Windows virtualization components and require a manual reboot. No automatic reboot will be issued. The first launch may require the user to create a Linux account. Do not collect its password.

Inside Ubuntu, if prerequisites are absent, the proposed privileged package installation is:

```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jre-headless python3-venv
```

Then `bash scripts/setup_linux.sh` creates only `.venv-linux`, installs the existing project dependencies, and registers a separate local kernel. The source checkout is reused through its mounted Windows path. Raw data is read, not copied or changed; 2022 is never included in development commands.

Official references: [Microsoft installation](https://learn.microsoft.com/en-us/windows/wsl/install), [command options](https://learn.microsoft.com/en-us/windows/wsl/basic-commands), [Ubuntu WSL installation](https://ubuntu.com/wsl/docs/stable/howto/install-ubuntu-wsl2/).

Linux setup, privileged installation and Linux execution are **not yet verified**. Windows analytical notebook evidence remains valid; storage acceptance remains blocked until a real round-trip succeeds.

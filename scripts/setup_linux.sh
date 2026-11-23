#!/usr/bin/env bash
# Reuse this project; do not install OS packages or change the Windows environment.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
python3 -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), 'Use Python 3.10-3.12 with pinned Spark 3.5.3'"
command -v java >/dev/null || { echo 'Java 17 is required; approve/install OS prerequisites first.' >&2; exit 1; }
python3 -m venv .venv-linux
.venv-linux/bin/python -m pip install -r requirements.txt
.venv-linux/bin/python -m ipykernel install --prefix .venv-linux --name python3 --display-name 'GridRescue Linux'
printf '%s\n' 'Project-local Linux setup completed. Run preflight before claiming persistence.'

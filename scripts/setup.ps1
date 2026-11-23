param([switch]$InstallDependencies)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot/..
if (-not $InstallDependencies) {
    throw 'Dependency installation requires approval. Rerun with -InstallDependencies after approval.'
}
$pythonPath = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $runtime = Get-Command python -ErrorAction SilentlyContinue
    if ($runtime) { $pythonPath = $runtime.Source }
}
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Python 3.10-3.12 is required.' }
& $pythonPath -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), 'Use Python 3.10-3.12 with PySpark 3.5'"
if ($LASTEXITCODE -ne 0) { throw 'Unsupported Python version; no environment modified.' }
& $pythonPath -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
& ./.venv/Scripts/python.exe scripts/patch_spark_worker.py
if ($LASTEXITCODE -ne 0) { throw 'Spark Windows worker compatibility backport failed' }
& ./.venv/Scripts/python.exe -m ipykernel install --prefix .venv --name python3 --display-name 'GridRescue (.venv)'
if ($LASTEXITCODE -ne 0) { throw 'kernel registration failed' }

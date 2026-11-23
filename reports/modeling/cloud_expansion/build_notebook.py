"""Build the self-contained Colab notebook from reviewed source and compact fixtures."""
import argparse
import base64
import hashlib
from io import BytesIO
from pathlib import Path
import textwrap
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import nbformat as nbf

from cloud_run import PACKAGE_FILES, ROOT


def package():
    out = BytesIO()
    with ZipFile(out, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for filename in PACKAGE_FILES:
            record = ZipInfo(filename)
            record.compress_type = ZIP_DEFLATED
            bundle.writestr(record, (ROOT / filename).read_bytes())
    return out.getvalue()


def create_notebook(output):
    notebook = nbf.v4.new_notebook(metadata={'kernelspec': {'display_name': 'Python 3', 'name': 'python3'},
                                             'colab': {'name': output.name},
                                             'language_info': {'name': 'python', 'version': '3.12'}})
    cells = notebook.cells

    def markdown(value):
        cells.append(nbf.v4.new_markdown_cell(textwrap.dedent(value).strip()))

    def code(value):
        cells.append(nbf.v4.new_code_cell(textwrap.dedent(value).strip()))

    markdown('''
    # GridRescue cloud expansion

    Reproduce the 20-county experiment, then compare larger training populations on the same 2021 rows. Start with a CPU runtime. The model uses the archived CPU settings even if a GPU is visible.

    Open this file in Colab using **File → Upload notebook**. The notebook contains the code and a small verification sample. Large source files travel from Figshare to Google Drive and then to Colab scratch space.

    **Start with cells 1–5.** They check the runtime, install the pinned environment, mount Drive, inspect public metadata, and reproduce a small trusted sample. Each expensive cell has its own switch and starts disabled. Read the preceding explanation before switching it on.
    ''')
    markdown('## 1. Inspect this runtime\n\nRead the available RAM and scratch disk, and note the Python version. Google Colab assigns resources dynamically.')
    code('''
    import os, platform, shutil, subprocess, sys
    from pathlib import Path

    VM = Path('/content/gridrescue_scratch')
    VM.mkdir(parents=True, exist_ok=True)
    print('Python:', platform.python_version(), 'CPU threads:', os.cpu_count())
    print('Free scratch disk GiB:', round(shutil.disk_usage(VM).free / 2**30, 2))
    memory_info = Path('/proc/meminfo').read_text().splitlines()
    print(next(line for line in memory_info if line.startswith('MemAvailable:')))
    for name in ('memory.max', 'memory.current'):
        stat = Path('/sys/fs/cgroup') / name
        if stat.exists():
            print(name, stat.read_text().strip(), 'bytes')
    if shutil.which('nvidia-smi'):
        subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], check=False)
    else:
        print('No NVIDIA GPU visible. The CPU runtime is appropriate.')
    ''')
    markdown('''
    ## 2. Unpack the bundled code and install the pinned dependencies

    This cell creates an isolated virtual environment under `/content`. The Spark package download can take a few minutes. Use a Python 3.12 runtime. If Java 17 is missing, set `INSTALL_JAVA17` to `True` and rerun this cell to install it in the VM.
    ''')
    bundle = package()
    sha = hashlib.sha256(bundle).hexdigest()
    code(f'''
    from base64 import b64decode
    from hashlib import sha256
    from io import BytesIO
    from zipfile import ZipFile

    BUNDLE_SHA = '{sha}'
    BUNDLE_B64 = """{base64.b64encode(bundle).decode('ascii')}"""
    packed = b64decode(BUNDLE_B64)
    if sha256(packed).hexdigest() != BUNDLE_SHA:
        raise RuntimeError('The bundled code checksum differs. Open a fresh copy of the notebook.')
    CODE_ROOT = Path('/content/gridrescue_cloud_code') / BUNDLE_SHA[:16]
    CODE_ROOT.mkdir(parents=True, exist_ok=True)
    with ZipFile(BytesIO(packed)) as archive:
        archive.extractall(CODE_ROOT)  # The checked bundle contains only reviewed project paths.
    SCRIPT_ROOT = CODE_ROOT / 'reports/modeling/cloud_expansion'
    del BUNDLE_B64, packed

    python312 = sys.executable if sys.version_info[:2] == (3, 12) else shutil.which('python3.12')
    if python312 is None:
        raise RuntimeError('Choose a Python 3.12 Colab runtime before continuing.')
    INSTALL_JAVA17 = False

    def java17():
        options = [p for p in Path('/usr/lib/jvm').glob('*/bin/java') if p.is_file()]
        if path := shutil.which('java'):
            options.insert(0, Path(path).resolve())
        for binary in options:
            result = subprocess.run([str(binary), '-version'], capture_output=True, text=True)
            if 'version "17.' in result.stderr + result.stdout:
                return binary.resolve()
        return None

    java = java17()
    if java is None and INSTALL_JAVA17:
        subprocess.run(['apt-get', '-qq', 'update'], check=True)
        subprocess.run(['apt-get', '-qq', 'install', '-y', 'openjdk-17-jre-headless'], check=True)
        java = java17()
    if java is None:
        raise RuntimeError('Java 17 is required. Set INSTALL_JAVA17=True and rerun cell 2.')
    STAGE_ENV = dict(os.environ, JAVA_HOME=str(java.parent.parent), PATH=str(java.parent) + os.pathsep + os.environ['PATH'])
    ENV = Path('/content/gridrescue_venvs') / BUNDLE_SHA[:16]
    ENV_PY = ENV / 'bin/python'
    if not ENV_PY.exists():
        subprocess.run([python312, '-m', 'venv', str(ENV)], check=True)
    if not (ENV / '.installed').exists():
        subprocess.run([str(ENV_PY), '-m', 'pip', 'install', '--disable-pip-version-check',
                        '-r', str(SCRIPT_ROOT / 'requirements-colab.txt')], check=True)
        subprocess.run([str(ENV_PY), '-m', 'pip', 'check'], check=True)
        (ENV / '.installed').touch()
    print('Pinned environment:', ENV_PY, 'Java:', java)
    ''')
    markdown('''
    ## 3. Mount Google Drive and choose a persistent folder

    Authorize Drive access when Colab asks. Use the same folder after a disconnection. Make at least 10 GiB available in Drive for raw files plus checkpoints. Spark and training work in VM scratch space.
    ''')
    code('''
    from google.colab import drive

    drive.mount('/content/drive')
    DRIVE = Path('/content/drive/MyDrive/GridRescueCloud')
    DRIVE.mkdir(parents=True, exist_ok=True)

    def stage(name, *options):
        command = [str(ENV_PY), '-u', str(SCRIPT_ROOT / 'cloud_run.py'), name,
                   '--vm', str(VM), '--drive', str(DRIVE), *options]
        subprocess.run(command, env=STAGE_ENV, check=True)

    stage('diagnostics')
    ''')
    markdown('## 4. Inspect the Figshare source\n\nThis cell requests the public article metadata for the pinned version and prints only the four development entries.')
    code("stage('metadata')")
    markdown('''
    ## 5. Reproduce a trusted sample

    The bundled source tokens come from the prior selected-county Bronze checkpoint. Compare all 24 predictors, exact labels and keys on 82 rows across 20 counties. Continue after this cell passes. It uses only the bundled fixture.
    ''')
    code("stage('fixture')")
    markdown('''
    ## 6. Download the four development CSVs inside Colab

    This starts a **4,413,747,290-byte** cloud transfer. The destination is Drive. Each finished file must match its pinned size, provider MD5 and trusted SHA-256. Partial files resume when the server honors byte ranges. An ignored range triggers a clean restart of that file.
    ''')
    code('''
    RUN_DOWNLOAD = False  # Change to True only when ready.
    if RUN_DOWNLOAD:
        stage('download', '--execute')
    else:
        print('Download skipped.')
    ''')
    markdown('''
    ## 7. Prepare the original cohort, Tier A

    Allow at least 7 GiB of available RAM and 15 GiB of free scratch to begin preprocessing. About 22 GiB scratch gives more headroom for both data stages in one session. The pipeline checks the exact 1,053,328 train and 582,532 development keys and labels, plus predictor values and null masks on stratified anchors from the full checkpoint. A mismatch halts the workflow.
    ''')
    code('''
    RUN_PILOT = False
    if RUN_PILOT:
        stage('pilot', '--execute')
    else:
        print('Pilot reconstruction skipped.')
    ''')
    markdown('''
    ## 8. Fit the Tier A benchmark and freeze the OOF thresholds

    Fit three expanding chronological folds and select the highest cutoffs that reach 40%, 50% and 60% recall. The final fit uses all Tier A training rows. Each completed fold and the final fit are checkpointed separately. Evaluation checks fitted preprocessing, exact same-runtime reload, and Windows metric tolerances. It reports cross-platform score and state deltas for review. Stop after Tier A for review.
    ''')
    code('''
    RUN_TIER_A = False
    if RUN_TIER_A:
        stage('train', '--tier', 'A', '--execute')
        stage('evaluate', '--tier', 'A')
    else:
        print('Tier A fit and evaluation skipped.')
    ''')
    markdown('''
    ## 9. Prepare the 3M and up-to-8M data tiers

    Select counties from training-period coverage only, balancing the order across regions and states. New York and all original geographic holdouts stay out of training. The dataset checkpoint records actual eligible counts and memory estimates. Tier B must fall in 2.8–3.2M; Tier C must add rows and stay at or below 8M.
    ''')
    code('''
    RUN_EXPANSION = False
    if RUN_EXPANSION:
        stage('expand', '--execute')
    else:
        print('Expansion preparation skipped.')
    ''')
    markdown('''
    ## 10. Fit and evaluate Tier B

    Continue after Tier A passes the benchmark parity check. Use the identical model feature list and XGBoost settings. The 2021 evaluation uses the same population and that tier’s frozen OOF cutoffs.
    ''')
    code('''
    RUN_TIER_B = False
    if RUN_TIER_B:
        stage('train', '--tier', 'B', '--execute')
        stage('evaluate', '--tier', 'B')
    else:
        print('Tier B fit and evaluation skipped.')
    ''')
    markdown('''
    ## 11. Optionally fit and evaluate Tier C

    Read the actual training count, encoded feature width and memory gate from cell 9. Allow roughly 24–32 GiB available RAM for a wide near-8M tier. If the gate fails, keep the completed Tier B or resume in a compatible high-memory runtime. This workflow keeps the same preprocessing and CPU XGBoost configuration.
    ''')
    code('''
    RUN_TIER_C = False
    if RUN_TIER_C:
        stage('train', '--tier', 'C', '--execute')
        stage('evaluate', '--tier', 'C')
    else:
        print('Optional Tier C fit and evaluation skipped.')
    ''')
    markdown('''
    ## 12. Export the comparison

    Set `EXPORT_TIERS` to the tiers that completed evaluation. The report combines AP, row-level decision metrics, geographic slices, descriptive matched-recall points and consecutive flag-run workload. The precision–recall plot marks the frozen operating points. The final checkpoint ZIP for each tier contains `pipeline.joblib`, `booster.ubj` and fit evidence.
    ''')
    code('''
    EXPORT_TIERS = []  # Example after two completed tiers: ['A', 'B']
    if EXPORT_TIERS:
        stage('export', '--tiers', *EXPORT_TIERS)
    else:
        print('Choose the completed tiers to export.')
    ''')
    markdown('''
    ## 13. Check progress and recover

    After reconnecting, use the same notebook, Python and Drive folder. Rerun cells 1–5, then resume your last enabled stage. `status` lists published archives. The stage verifies the archive and its payload when restoring it. Partial downloads stay under the versioned raw folder. If a checksum fails, inspect the named file before moving it aside. Transfer the compact `comparison-*.zip` or `tier-*-final.zip` back to your computer from Drive. Keep the experiment folders if you plan to resume.

    The 2021 results are previously consulted development evidence. Consecutive flagged rows are grouped as a workload proxy. Incident-level labels would be needed to measure real outage alert performance.
    ''')
    code("stage('status')")
    nbf.validate(notebook)
    nbf.write(notebook, output)
    print(f'{output}: {len(cells)} cells; source ZIP {len(bundle):,} bytes; notebook {output.stat().st_size:,} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'notebooks/colab_gridrescue_large_scale.ipynb')
    create_notebook(parser.parse_args().output)

"""Execute the two discussion notebooks with fail-fast errors and saved output."""
import os
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mode',choices=['memory','parquet','arrow-local'],default=os.environ.get('GRIDRESCUE_STORAGE_MODE','arrow-local' if os.name=='nt' else 'parquet'))
parser.add_argument('--output-dir',type=Path,default=Path('notebooks'))
parser.add_argument('--report',type=Path,default=Path('reports/notebook_execution.json'))
parser.add_argument('--notebook',action='append',choices=['task1_eda','task2_preprocessing','task3_modeling'])
args=parser.parse_args()
output_dir=(ROOT/args.output_dir).resolve()
report_path=(ROOT/args.report).resolve()
if not output_dir.is_relative_to(ROOT) or not report_path.is_relative_to(ROOT):
    raise ValueError('Notebook outputs and reports must remain inside this project')
output_dir.mkdir(parents=True,exist_ok=True)
report_path.parent.mkdir(parents=True,exist_ok=True)
os.environ['GRIDRESCUE_STORAGE_MODE']=args.mode
os.environ.setdefault('JUPYTER_PLATFORM_DIRS','1')
os.environ.setdefault('IPYTHONDIR',str(ROOT/'artifacts/ipython'))
os.environ.setdefault('JUPYTER_RUNTIME_DIR',str(ROOT/'artifacts/jupyter'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'artifacts/matplotlib'))
os.environ['JUPYTER_PATH'] = str(Path(sys.prefix)/'share/jupyter')
execution_report={'started_utc':datetime.now(timezone.utc).isoformat(),'executor_python':sys.executable,
                  'mode':args.mode,'clean_kernel_per_notebook':True,'notebooks':[]}
if report_path.exists():
    history=ROOT/'artifacts/notebook_execution_history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    history.mkdir(parents=True,exist_ok=True)
    shutil.copy2(report_path,history/report_path.name)
failed=False
for name in args.notebook or ['task1_eda','task2_preprocessing']:
    path=ROOT/'notebooks'/f'{name}.ipynb'
    destination=output_dir/path.name
    if destination.exists():
        history=ROOT/'artifacts/notebook_execution_history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        history.mkdir(parents=True,exist_ok=True)
        shutil.copy2(destination,history/destination.name)
    notebook=nbformat.read(path,as_version=4)
    nbformat.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type=='code':
            cell.outputs=[]
            cell.execution_count=None
    client=NotebookClient(notebook,timeout=1800,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}})
    item={'name':name,'status':'RUNNING'}
    execution_report['notebooks'].append(item)
    try:
        client.execute()
        code_cells=[cell for cell in notebook.cells if cell.cell_type=='code']
        assert all(cell.execution_count is not None for cell in code_cells)
        assert not any(o.output_type=='error' for cell in code_cells for o in cell.outputs)
        item.update(status='VERIFIED',executed_code_cells=len(code_cells),completed_utc=datetime.now(timezone.utc).isoformat())
    except Exception as error:
        item.update(status='FAILED',error=repr(error))
        failed=True
        print(f'Failed {path.name}: {error}',flush=True)
    finally:
        # Partial output/error is evidence, not a successful execution claim.
        nbformat.write(notebook,destination)
        report_path.write_text(json.dumps(execution_report,indent=2)+'\n',encoding='utf-8')
    if item['status']=='VERIFIED':
        print(f'Executed {path.name}',flush=True)
raise SystemExit(int(failed))

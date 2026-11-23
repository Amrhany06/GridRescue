"""Execute/reuse only approved development experiments; never open 2022."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.experiment import run_development

if __name__=='__main__':
    result=run_development(ROOT)
    print(result['status'],result['frozen_selection'],flush=True)

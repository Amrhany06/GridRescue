"""Evaluate frozen winner once. Completed evaluations replay saved evidence."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.final_evaluation import run_final,verify_reload

if __name__=='__main__':
    print(run_final(ROOT)['metrics'])
    print(verify_reload(ROOT))

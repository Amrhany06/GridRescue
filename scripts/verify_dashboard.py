"""Verify real app controls/chart data and the running local HTTP service."""
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    path=ROOT/'reports/dashboard_functional_tests.txt'
    with path.open('w',encoding='utf-8') as log:
        tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_dashboard.py','-v'],
                             cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    health=None
    try:
        with urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=10) as response:
            health=response.status
    except OSError:
        pass
    status='VERIFIED' if tests.returncode==0 and health==200 else 'FAILED'
    report={'status':status,'completed_utc':datetime.now(timezone.utc).isoformat(),
            'test_exit_code':tests.returncode,'health_http_status':health,'url':'http://127.0.0.1:8501',
            'verified':['FIPS-keyed source/audit reconciliation','default KPIs','state/county/date/severity filters',
                        'filtered chart Arrow datasets agree with source aggregates','empty results','scope switching','independent-city identity'],
            'visual_browser_review':{'status':'BLOCKED','reason':'Computer Use stopped because it could not determine the Windows browser URL with sufficient confidence; no alternative UI automation used to bypass that policy.'},
            'model_results':'NOT AVAILABLE: scientific approval/training pending','live_monitoring':False}
    (ROOT/'reports/dashboard_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return int(status!='VERIFIED')


if __name__=='__main__':
    raise SystemExit(main())

"""Load only reconciled, verified historical aggregates; never open raw sources."""
import json
import hashlib
from pathlib import Path
import pandas as pd

SCOPES={
    'Selected counties (full development years)':'county',
    'January prefix (debugging subset)':'sample',
}


def load_scope(root:Path,scope:str):
    if scope not in SCOPES.values():
        raise ValueError('Unknown historical scope')
    directory=root/'reports/dashboard'/scope
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status')!='VERIFIED':
        raise ValueError('Dashboard export is not verified')
    audit_path=root/'reports/memory'/scope/'audit.json'
    if hashlib.sha256(audit_path.read_bytes()).hexdigest()!=manifest['source_audit_sha256']:
        raise ValueError('Dashboard export is stale relative to its audit')
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if not audit.get('execution','').startswith('VERIFIED IN-MEMORY AUDIT ONLY'):
        raise ValueError('Aggregate execution is not verified')
    if hashlib.sha256((directory/'daily.csv').read_bytes()).hexdigest()!=manifest['csv_sha256']:
        raise ValueError('Dashboard CSV hash mismatch')
    data=pd.read_csv(directory/'daily.csv',parse_dates=['date'],dtype={'fips_code':'string'})
    required={'fips_code','state','county','date','observations','mean_customers_out','peak_customers_out','sum_customer_observations'}
    if not required.issubset(data.columns) or data.empty:
        raise ValueError('Aggregate schema or content is invalid')
    if data['date'].isna().any() or not data['date'].dt.year.between(2018,2021).all():
        raise ValueError('Only development-period aggregates may be displayed')
    if data.duplicated(['fips_code','date']).any() or data[['fips_code','state','county']].isna().any().any():
        raise ValueError('Duplicate or missing county-day identity')
    if int(data.observations.sum())!=audit['counts']['silver']:
        raise ValueError('Aggregate observations do not reconcile to the verified audit')
    if not data.observations.between(1,96).all():
        raise ValueError('Invalid observed county-day slot count')
    if (data[['sum_customer_observations','peak_customers_out','mean_customers_out']]<0).any().any():
        raise ValueError('Negative historical count aggregate')
    data['county_label']=data['county']+', '+data['state']
    identities=data[['fips_code','county_label']].drop_duplicates().groupby('county_label').size()
    collision=data['county_label'].map(identities)>1
    data.loc[collision,'county_label']=data.loc[collision,'county']+' ['+data.loc[collision,'fips_code']+'], '+data.loc[collision,'state']
    return data,audit


def daily_trend(data):
    result=data.groupby('date')[['observations','sum_customer_observations']].sum().sort_index()
    result['mean_customers_out']=result.sum_customer_observations/result.observations
    return result


def load_model_result(root:Path):
    directory=root/'reports/modeling'
    path=directory/'final_evaluation.json'
    if not path.exists():
        return None
    result=json.loads(path.read_text(encoding='utf-8'))
    journal=json.loads((directory/'final_evaluation_journal.json').read_text(encoding='utf-8'))
    if journal.get('status')!='COMPLETE' or result.get('status')!='VERIFIED_FINAL_EVALUATION' or result.get('final_evaluation_count')!=1:
        raise ValueError('Model evaluation is not completed')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=journal['result_sha256']:
        raise ValueError('Model evaluation evidence hash mismatch')
    reload=json.loads((directory/'reload_validation.json').read_text(encoding='utf-8'))
    if reload.get('status')!='VERIFIED' or reload.get('artifact_sha256')!=result['artifact_sha256']:
        raise ValueError('Model reload evidence is absent or does not match')
    return result

"""Reproducible development experiment; 2022 access lives only in final_evaluation."""
import hashlib
import importlib.metadata
import json
import statistics
import sys
import time
import warnings
from datetime import datetime,timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .modeling import FEATURE_COLUMNS,MODEL_NAMES,SEARCH,make_model,chronological_folds,classification_metrics,validate_development
from .storage import MANIFEST, scope_paths


def write_json(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def slug(name):
    return name.lower().replace(' ','_')


def progress(root,stage,detail):
    item={'utc':datetime.now(timezone.utc).isoformat(),'stage':stage,'detail':detail}
    write_json(root/'reports/modeling/progress.json',item)
    with (root/'reports/modeling/progress.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(item)+'\n')
    print(json.dumps(item),flush=True)


def approved(root):
    """Read the approved label and population settings before opening development data."""
    approval=json.loads((root/'reports/target_approval.json').read_text(encoding='utf-8'))
    if approval.get('status')!='APPROVED_CONDITIONAL_EXPERIMENT':
        raise PermissionError('Explicit scientific approval required')
    assert approval['county_fips']==['06037','12086','48201']
    assert approval['required_future_quarter_hours']==12
    assert approval['minimum_absolute_increase']==200 and approval['minimum_relative_increase']==0.5
    return approval


def add_missing_flags(frame):
    """Copy the input and mark which exact historical predictors are absent."""
    frame=frame.copy()
    for column in ['lag_15m','lag_60m','delta_60m']:
        frame[column+'_missing']=frame[column].isna().astype(float)
    return frame


def development_source(root):
    """Return verified county paths and Parquet hashes for the bounded ML read."""
    proof = json.loads((root / 'reports/persistence_validation.json').read_text(encoding='utf-8'))
    backend = proof.get('storage_backend')
    if proof.get('status') != 'VERIFIED' or backend not in {'native', 'arrow-local'}:
        raise RuntimeError('Task 2 county persistence must be verified before development')
    paths = scope_paths(root, 'county', backend)
    directory = paths['label_audit']
    county_proof = proof['scopes']['county']
    row_count = county_proof['persisted_stage_counts']['label_audit']
    comparison = county_proof['full_content_roundtrips'][directory.relative_to(root).as_posix()]
    if (comparison['rows'] != row_count or comparison['missing_or_changed_rows']
            or comparison['extra_or_changed_rows'] or not 0 < row_count <= 500_000):
        raise ValueError('County label audit failed content reconciliation or exceeded the local row budget')
    parts = sorted(directory.glob('*.parquet'))
    if not parts:
        raise FileNotFoundError(f'No verified county Parquet parts in {directory}')
    if any(part.resolve().parent != directory.resolve() for part in parts):
        raise ValueError('County Parquet part resolves outside its directory')
    hashes = [(part.name, digest(part)) for part in parts]
    if backend == 'arrow-local':
        manifest = json.loads((directory / MANIFEST).read_text(encoding='utf-8'))
        if manifest['format'] != 'gridrescue-arrow-local-v1' or manifest['rows'] != row_count:
            raise ValueError('Unexpected Arrow-local format or county row count')
        expected = sorted((part['name'], part['sha256']) for part in manifest['parts'])
        if hashes != expected:
            raise ValueError('County Parquet hash mismatch')
    return paths, hashes, row_count


def load_development(root):
    """Read verified county data and return ordered, eligible 2018–2021 anchors."""
    approved(root)
    paths, parts, row_count = development_source(root)
    fields = ['fips_code', 'timestamp', 'split', 'candidate_y', 'label_complete',
              'future_slots', *FEATURE_COLUMNS[:10]]
    frame = pd.read_parquet([paths['label_audit'] / name for name, _ in parts], columns=fields)
    if len(frame) != row_count:
        raise ValueError('County input row count differs from the verified persistence report')
    frame['timestamp']=pd.to_datetime(frame['timestamp'],utc=True)
    validate_development(frame)
    if set(frame.fips_code)!=set(['06037','12086','48201']):
        raise ValueError('Unexpected modeling population')
    if frame.duplicated(['fips_code','timestamp']).any():
        raise ValueError('Duplicate county-time key in Gold')
    # A missing y is a rejected anchor, never an example of class zero.
    frame=frame[frame.candidate_y.notna() & frame.split.isin(['train','validation'])].copy()
    expected_split = np.where(frame.timestamp.dt.year <= 2020, 'train', 'validation')
    if not frame.split.eq(expected_split).all():
        raise ValueError('Development split does not match the UTC anchor year')
    assert frame.label_complete.eq(True).all() and (frame.future_slots==12).all() and (frame.customers_out_t>0).all()
    assert (frame.candidate_y.isin([0,1])).all()
    assert not ((frame.split=='train') & (frame.timestamp+pd.Timedelta(hours=3)>=pd.Timestamp('2021-01-01',tz='UTC'))).any()
    assert not ((frame.split=='validation') & (frame.timestamp+pd.Timedelta(hours=3)>=pd.Timestamp('2022-01-01',tz='UTC'))).any()
    frame=add_missing_flags(frame).sort_values(['timestamp','fips_code']).reset_index(drop=True)
    frame['candidate_y']=frame.candidate_y.astype(int)
    for column in FEATURE_COLUMNS:
        frame[column]=pd.to_numeric(frame[column],errors='raise').astype(float)
    predictors = frame[FEATURE_COLUMNS]
    if np.isinf(predictors.to_numpy()).any() or predictors.isna().all().any():
        raise ValueError('Infinite predictor value or entirely missing predictor')
    audit=json.loads((paths['report']/'audit.json').read_text(encoding='utf-8'))
    expected={row['split']:row['count'] for row in audit['eligible_preparation_counts']}
    assert frame.groupby('split').size().to_dict()==expected
    assert len(frame)==406240
    return frame


def fingerprint(root):
    """Hash the verified development inputs and settings used for cache checks."""
    paths, parts, _ = development_source(root)
    payload={'data':parts, 'data_path':paths['label_audit'].relative_to(root).as_posix(),
             'code':[(name,digest(Path(__file__).parent/name)) for name in ['modeling.py','experiment.py']],
             'approval':digest(root/'reports/target_approval.json'),
             'models':MODEL_NAMES,'features':FEATURE_COLUMNS,'search':SEARCH,
             'versions':{name:importlib.metadata.version(name) for name in ['scikit-learn','numpy','pandas','joblib']}}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),payload


def fit(model,x,y):
    """Fit a fresh pipeline on X and y, returning elapsed seconds and warnings."""
    if x.isna().all().any():
        raise ValueError('Every predictor needs at least one observed value in this training partition')
    start=time.perf_counter()
    with warnings.catch_warnings(record=True) as caught,threadpool_limits(limits=2):
        warnings.simplefilter('always')
        model.fit(x,y)
    messages=[str(w.message) for w in caught]
    for message in messages:
        print('Recorded training warning: '+message,flush=True)
    return time.perf_counter()-start,messages


def probability(model,x):
    """Return the fitted pipeline's class-1 scores in input row order."""
    with threadpool_limits(limits=2):
        # classes_ tells us which predict_proba column contains class 1.
        return model.predict_proba(x)[:,list(model.classes_).index(1)]


def full_fit(root,frame,name,parameters,kind,run_hash):
    """Fit one named configuration on 2018–2020 and score train and 2021."""
    report_path=root/'reports/modeling'/f'{slug(name)}_{kind}.json'
    artifact=root/'artifacts/modeling'/f'{slug(name)}_{kind}.joblib'
    if report_path.exists():
        cached=json.loads(report_path.read_text(encoding='utf-8'))
        predictions = root / cached['predictions']
        if (cached.get('fingerprint') == run_hash and artifact.exists()
                and digest(artifact) == cached.get('artifact_sha256') and predictions.exists()
                and digest(predictions) == cached.get('predictions_sha256')):
            return cached
    train=frame[frame.split=='train']
    validation=frame[frame.split=='validation']
    progress(root,'full_training',{'model':name,'kind':kind,'parameters':parameters,'rows':len(train)})
    model=make_model(name,parameters)
    elapsed,messages=fit(model,train[FEATURE_COLUMNS],train.candidate_y)
    train_p=probability(model,train[FEATURE_COLUMNS])
    val_p=probability(model,validation[FEATURE_COLUMNS])
    assert model.named_steps['classifier'].n_features_in_==13
    artifact.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(model,artifact,compress=3)
    prediction=validation[['fips_code','timestamp','candidate_y']].copy()
    prediction['probability']=val_p
    prediction['prediction']=(val_p>0.5).astype(int)
    predictions_path=artifact.with_name(artifact.stem+'_validation_predictions.parquet')
    prediction.to_parquet(predictions_path,index=False)
    result={'model':name,'kind':kind,'parameters':parameters,'classifier_parameters':model.named_steps['classifier'].get_params(),
            'fingerprint':run_hash,'fit_seconds':elapsed,'warnings':messages,
            'train':classification_metrics(train.candidate_y,train_p),'validation':classification_metrics(validation.candidate_y,val_p),
            'artifact':artifact.relative_to(root).as_posix(),'artifact_sha256':digest(artifact),
            'predictions':predictions_path.relative_to(root).as_posix(),'predictions_sha256':digest(predictions_path)}
    write_json(report_path,result)
    return result


def cross_validate(root,frame,folds,name,parameters,run_hash):
    """Fit a fresh pipeline per fold and return metric means and sample deviations."""
    key=hashlib.sha256(json.dumps({'name':name,'parameters':parameters},sort_keys=True).encode()).hexdigest()[:12]
    path=root/'reports/modeling/cv'/f'{slug(name)}_{key}.json'
    if path.exists():
        cached=json.loads(path.read_text(encoding='utf-8'))
        if cached.get('fingerprint')==run_hash:
            return cached
    results=[]
    for fold in folds:
        # iloc selects the integer row positions assigned to each chronological block.
        train,validation=frame.iloc[fold['train']],frame.iloc[fold['validation']]
        progress(root,'cross_validation',{'model':name,'parameters':parameters,'fold':fold['name'],'train':len(train),'validation':len(validation)})
        model=make_model(name,parameters)  # Starts with unfitted imputer, scaler and classifier.
        elapsed,messages=fit(model,train[FEATURE_COLUMNS],train.candidate_y)
        results.append({'name':fold['name'],'train_rows':len(train),'validation_rows':len(validation),
                        'last_training_anchor':train.timestamp.max().isoformat(),'first_validation_anchor':validation.timestamp.min().isoformat(),
                        'embargo_seconds':float((validation.timestamp.min()-train.timestamp.max()).total_seconds()),
                        'fit_seconds':elapsed,'warnings':messages,
                        'train':classification_metrics(train.candidate_y,probability(model,train[FEATURE_COLUMNS])),
                        'validation':classification_metrics(validation.candidate_y,probability(model,validation[FEATURE_COLUMNS]))})
    summary={}
    for metric in ['average_precision','pr_auc_trapezoid','roc_auc','accuracy','precision','recall','f1']:
        values=[r['validation'][metric] for r in results]
        summary[metric]={'mean':statistics.mean(values),'std':statistics.stdev(values)}
    result={'model':name,'parameters':parameters,'fingerprint':run_hash,'folds':results,'summary':summary,
            'total_fit_seconds':sum(r['fit_seconds'] for r in results)}
    write_json(path,result)
    return result


def run_development(root):
    """Run or reuse the baselines, fold scores and tuning, then record the 2021 choice."""
    root=Path(root).resolve()
    frame=load_development(root)
    run_hash,inputs=fingerprint(root)
    out=root/'reports/modeling/development.json'
    if out.exists():
        cached=json.loads(out.read_text(encoding='utf-8'))
        if cached.get('status')=='VERIFIED_DEVELOPMENT' and cached.get('fingerprint')==run_hash:
            return cached
        if (root/'reports/modeling/final_evaluation_journal.json').exists():
            raise RuntimeError('Development changed after final-test access. Do not silently retrain/re-evaluate.')
    # All real default full-training baselines precede all CV and tuning.
    defaults=[full_fit(root,frame,name,{},'default',run_hash) for name in MODEL_NAMES]
    folds=chronological_folds(frame)
    default_cv=[cross_validate(root,frame,folds,name,{},run_hash) for name in MODEL_NAMES]
    searches=[]
    selected=[]
    for baseline,base_cv,name in zip(defaults,default_cv,MODEL_NAMES):
        options=[base_cv]
        for parameters in SEARCH[name]:
            parameters=dict(parameters)
            if name=='Logistic Regression' and any('converg' in message.lower() for message in baseline['warnings']):
                parameters['max_iter']=1000
            options.append(cross_validate(root,frame,folds,name,parameters,run_hash))
        best=max(options,key=lambda r:(r['summary']['average_precision']['mean'],-len(r['parameters'])))
        chosen=baseline if not best['parameters'] else full_fit(root,frame,name,best['parameters'],'cv_selected',run_hash)
        searches.append({'model':name,'candidates':options,'selected_parameters':best['parameters'],'selected_cv':best['summary']})
        selected.append({'model':name,'parameters':best['parameters'],'cv':best,'full_fit':chosen})
    winner=max(selected,key=lambda r:(r['full_fit']['validation']['average_precision'],-MODEL_NAMES.index(r['model'])))
    selection={'frozen':True,'utc':datetime.now(timezone.utc).isoformat(),'model':winner['model'],'parameters':winner['parameters'],
               'fingerprint':run_hash,'features':FEATURE_COLUMNS,'selection_rule':'Highest 2021 average precision among training-CV-selected configurations; model-order tie break',
               'validation_average_precision':winner['full_fit']['validation']['average_precision'],
               'test_inspected_for_selection':False,'final_evaluation_limit':1}
    write_json(root/'reports/modeling/frozen_selection.json',selection)
    comparison=[]
    for baseline,cv,choice in zip(defaults,default_cv,selected):
        for label,model_result,cv_result in [('default',baseline,cv),('CV selected',choice['full_fit'],choice['cv'])]:
            comparison.append({'model':baseline['model'],'version':label,'parameters':model_result['parameters'],
                               'cv_average_precision_mean':cv_result['summary']['average_precision']['mean'],
                               'cv_average_precision_std':cv_result['summary']['average_precision']['std'],
                               'fit_seconds':model_result['fit_seconds'],'train_average_precision':model_result['train']['average_precision'],
                               **model_result['validation']})
    result={'status':'VERIFIED_DEVELOPMENT','utc':datetime.now(timezone.utc).isoformat(),'fingerprint':run_hash,'inputs':inputs,
            'rows':frame.groupby('split').size().to_dict(),'default_baselines':defaults,'default_cv':default_cv,'searches':searches,
            'selected':selected,'comparison':comparison,'frozen_selection':selection,
            'primary_metric':'average_precision; trapezoidal PR-AUC reported separately',
            'limitations':['Three-county retrospective complete-case cohort','99.80% overlapping eligible windows; folds are not independent event samples',
                           'Numeric calendar encoding is a baseline; no target-driven feature selection','2022 has not been used in model selection or tuning']}
    write_json(out,result)
    pd.DataFrame(comparison).drop(columns=['confusion_matrix']).to_csv(root/'reports/modeling/comparison.csv',index=False)
    progress(root,'development_complete',selection)
    return result

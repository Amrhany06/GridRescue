"""Approved experiment utilities. No import-time data access or model fitting."""
import json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score,precision_score,recall_score,f1_score,confusion_matrix,
                             roc_auc_score,average_precision_score,precision_recall_curve,auc)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS=['customers_out_t','lag_15m','lag_60m','delta_60m','rolling_mean_60m',
                 'rolling_variance_60m','history_slots_60m','hour_utc','weekday_utc','month_utc',
                 'lag_15m_missing','lag_60m_missing','delta_60m_missing']
MODEL_NAMES=['Logistic Regression','Decision Tree','Random Forest']
SEARCH={
    'Logistic Regression':[{'C':0.1},{'C':10.0}],
    'Decision Tree':[
        {'max_depth':12,'min_samples_split':2,'min_samples_leaf':1},
        {'max_depth':20,'min_samples_split':2,'min_samples_leaf':1},
        {'max_depth':12,'min_samples_split':20,'min_samples_leaf':1},
        {'max_depth':12,'min_samples_split':2,'min_samples_leaf':10}],
    'Random Forest':[
        {'n_estimators':100,'max_depth':12,'min_samples_leaf':5},
        {'n_estimators':200,'max_depth':12,'min_samples_leaf':5},
        {'n_estimators':100,'max_depth':20,'min_samples_leaf':5},
        {'n_estimators':100,'max_depth':12,'min_samples_leaf':10}],
}


def validate_development(frame):
    """Check that the modeling table has valid UTC timestamps in 2018–2021 only."""
    times=pd.to_datetime(frame['timestamp'],utc=True)
    if times.isna().any() or not times.dt.year.between(2018,2021).all():
        raise ValueError('Development must contain 2018–2021 only; 2022 is sealed')


def chronological_folds(frame):
    """Return three expanding train/validation index pairs with a label-horizon embargo."""
    validate_development(frame)
    times=pd.to_datetime(frame['timestamp'],utc=True)
    horizon=pd.Timedelta(hours=3)
    windows=[('2018_H2','2018-07-01','2019-01-01'),('2019','2019-01-01','2020-01-01'),('2020','2020-01-01','2021-01-01')]
    result=[]
    for name,start,end in windows:
        start,end=pd.Timestamp(start,tz='UTC'),pd.Timestamp(end,tz='UTC')
        # flatnonzero turns each Boolean time mask into integer row positions.
        train=np.flatnonzero((times+horizon<start).to_numpy())
        validation=np.flatnonzero(((times>=start)&(times+horizon<end)).to_numpy())
        if not len(train) or not len(validation):
            raise ValueError(f'Empty chronological fold: {name}')
        for indices in [train,validation]:
            if frame.iloc[indices]['candidate_y'].nunique()!=2:
                raise ValueError(f'Both classes required in fold {name}')
        assert times.iloc[train].max()+horizon<times.iloc[validation].min()
        result.append({'name':name,'train':train,'validation':validation,'validation_start':start.isoformat(),'validation_end':end.isoformat()})
    return result


def make_model(name,parameters=None):
    """Build an unfitted imputer, scaler and named classifier using ordered numeric inputs."""
    if name=='Logistic Regression':
        estimator=LogisticRegression(random_state=17)
    elif name=='Random Forest':
        estimator=RandomForestClassifier(random_state=17,n_jobs=2)
    elif name=='Decision Tree':
        estimator=DecisionTreeClassifier(random_state=17)
    else:
        raise ValueError(f'Unknown model: {name}')
    if parameters:
        estimator.set_params(**parameters)
    # Fit the medians before fitting the scaler on the resulting filled-in values.
    numeric=Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler())])
    prepare=ColumnTransformer([('numeric',numeric,FEATURE_COLUMNS)],remainder='drop')
    return Pipeline([('prepare',prepare),('classifier',estimator)])


def classification_metrics(y,probabilities):
    """Return threshold metrics and, for two-class cohorts, ranking metrics."""
    y=np.asarray(y,dtype=int)
    probabilities=np.asarray(probabilities,dtype=float)
    if len(y)!=len(probabilities) or not len(y) or not np.isfinite(probabilities).all():
        raise ValueError('Invalid prediction array')
    prediction=(probabilities>0.5).astype(int)
    two_classes=len(np.unique(y))==2
    result={'rows':len(y),'positive':int(y.sum()),'prevalence':float(y.mean()),
            'accuracy':float(accuracy_score(y,prediction)),'precision':float(precision_score(y,prediction,zero_division=0)),
            'recall':float(recall_score(y,prediction,zero_division=0)),'f1':float(f1_score(y,prediction,zero_division=0)),
            'confusion_matrix':confusion_matrix(y,prediction,labels=[0,1]).tolist(),
            'roc_auc':float(roc_auc_score(y,probabilities)) if two_classes else None,
            'average_precision':float(average_precision_score(y,probabilities)) if two_classes else None,
            'pr_auc_trapezoid':None,'decision_threshold':0.5,'tie_rule':'Class 0 at exactly 0.5, matching sklearn binary argmax'}
    if two_classes:
        precision,recall,_=precision_recall_curve(y,probabilities)
        result['pr_auc_trapezoid']=float(auc(recall,precision))
    else:
        result['ranking_metric_note']='Undefined for this single-class cohort; not fabricated.'
    return result


def claim_final_evaluation(path,selection):
    if not selection.get('frozen'):
        raise ValueError('Final evaluation requires a frozen development selection')
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation is the once-only boundary, before opening held-out data.
    with path.open('x',encoding='utf-8') as stream:
        json.dump({'status':'STARTED','utc':datetime.now(timezone.utc).isoformat(),'selection':selection},stream,indent=2)

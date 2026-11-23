"""Historical data viewer. No predictions exist until scientific target approval."""
import json
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.dashboard_data import load_scope, daily_trend, SCOPES
st.set_page_config(page_title='GridRescue | Historical outages',layout='wide')
st.title('GridRescue')
st.write('Explore reported county electricity outages in the development sample. Counts describe customers without electricity at observation times.')
st.warning('Historical sample only. Missing county-time rows are unknown, not zero. No validated prediction model is available.')
@st.cache_data
def load_data(scope,version):
    return load_scope(ROOT,scope)

with st.sidebar:
    st.header('Explore observations')
    label=st.selectbox('Data scope',list(SCOPES))
scope=SCOPES[label]
directory=ROOT/'reports/dashboard'/scope
try:
    version=tuple((directory/name).stat().st_mtime_ns for name in ['daily.csv','manifest.json'])+((ROOT/'reports/memory'/scope/'audit.json').stat().st_mtime_ns,)
    data,audit=load_data(scope,version)
except (OSError,ValueError,KeyError) as error:
    st.error(f'Verified historical data could not be loaded: {error}')
    st.info('Generate the matching in-memory audit, then run scripts/export_dashboard.py to create verified FIPS-keyed dashboard data.')
    st.stop()
st.caption('Scope: '+audit['scope'])
with st.sidebar:
    states=st.multiselect('States',sorted(data.state.unique()),key=scope+'_states')
    if states:
        data=data[data.state.isin(states)]
    county_options=sorted(data.county_label.unique())
    county_key=scope+'_counties'
    if county_key in st.session_state:
        retained=[c for c in st.session_state[county_key] if c in county_options]
        if retained!=st.session_state[county_key]:
            st.session_state[county_key]=retained
    counties=st.multiselect('Counties',county_options,key=county_key)
    if counties:
        data=data[data.county_label.isin(counties)]
    if data.empty:
        st.info('No rows match those filters. Clear a filter to continue.')
        st.stop()
    dates=st.date_input('Observation dates',value=(data.date.min().date(),data.date.max().date()),key=scope+'_dates')
    minimum=st.number_input('Minimum daily peak customers out',min_value=0,value=0,key=scope+'_severity')
if not isinstance(dates,(tuple,list)) or len(dates)!=2:
    st.info('Choose both a start date and an end date to display observations.')
    st.stop()
if len(dates)==2:
    data=data[data.date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))]
data=data[data.peak_customers_out>=minimum]
if data.empty:
    st.info('No observations match these filters. Widen the dates or reduce the minimum peak.')
    st.stop()
st.subheader('Selected observations')
columns=st.columns(4)
columns[0].metric('County-time observations',f'{int(data.observations.sum()):,}')
columns[1].metric('Observed county-days',f'{len(data):,}')
columns[2].metric('Highest reported customers out',f'{int(data.peak_customers_out.max()):,}')
columns[3].metric('Slots within observed days',f'{data.observations.sum()/(96*len(data)):.2%}')
st.caption('Slot coverage uses only county-days with observations. Entirely absent days are excluded, never converted to zero.')
trend=daily_trend(data)
st.subheader('Reported outage size over time')
if scope=='sample':
    st.scatter_chart(trend[['mean_customers_out']])
else:
    st.line_chart(trend[['mean_customers_out']])
st.caption('Weighted mean per observed county-time row. Coverage varies; a drop does not establish restoration or fewer affected people.')
st.subheader('Coverage over time')
st.bar_chart(trend[['observations']])
st.subheader('Observed county comparisons')
county_summary=data.groupby('county_label').agg(observations=('observations','sum'),peak_customers_out=('peak_customers_out','max'))
st.bar_chart(county_summary.sort_values('observations',ascending=False).head(15)[['observations']])
st.subheader('Findings for this selection')
peak=data.loc[data.peak_customers_out.idxmax()]
st.write(f"The highest observed count is {int(peak.peak_customers_out):,} in {peak.county_label} on {peak.date:%Y-%m-%d}. It is a reported count, not an inferred outage cause or unique affected-customer total.")
st.write('Every source year ends at December 31 00:00 UTC. Low coverage on that date is source truncation, not evidence of restoration. The selected counties and January prefixes have different eligibility and severity distributions.')
st.subheader('Prediction status')
from gridrescue.dashboard_data import load_model_result
try:
    model_result=load_model_result(ROOT)
except (OSError,ValueError,KeyError) as error:
    model_result=None
    st.warning(f'Model evidence is unavailable: {error}')
if model_result is None:
    st.info('The three-county experiment is approved. No completed, reload-verified final model result is available yet.')
else:
    st.write('Experimental classifier: '+model_result['selection']['model'])
    st.caption('Frozen 2022 holdout results below describe the full eligible three-county test cohort. Historical chart filters do not rescore or change this cohort.')
    metrics=model_result['metrics']
    st.table(pd.DataFrame([{'Eligible test anchors':metrics['rows'],'Positive fraction':metrics['prevalence'],
        'Accuracy':metrics['accuracy'],'Precision':metrics['precision'],'Recall':metrics['recall'],
        'F1':metrics['f1'],'ROC-AUC':metrics['roc_auc'],'Average precision':metrics['average_precision'],
        'Trapezoidal PR-AUC':metrics['pr_auc_trapezoid']}]))
    with st.expander('Final model diagnostics and limitations'):
        st.write('Confusion matrix: rows are observed class; columns are predicted class. Class order: 0, 1.')
        st.table(pd.DataFrame(metrics['confusion_matrix'],index=['Observed 0','Observed 1'],columns=['Predicted 0','Predicted 1']))
        st.write('Complete-case selection, overlapping three-hour windows and three-county sampling limit generalization. This is a historical university experiment; operational validity is not established.')
        st.json(model_result['county_metrics'])
st.subheader('County and date details')
st.dataframe(data.sort_values(['date','state','county']),hide_index=True,width='stretch')
st.download_button('Download filtered observations',data.to_csv(index=False),'gridrescue_filtered.csv','text/csv')
with st.expander('Quality decisions and measured findings'):
    st.write(audit.get('scope'))
    st.json(audit.get('counts',{}))
    st.write(audit.get('gap_policy'))
    st.write(audit.get('outliers',{}))
    st.write('Provisional labels require 12 future quarter-hour slots; absent observations remain unknown. 2022 is sealed from development.')
st.link_button('ORNL EAGLE-I source dataset','https://figshare.com/articles/dataset/24237376')
st.caption('Source: ORNL EAGLE-I, Figshare dataset 24237376. This page is not live grid monitoring. Repeated observations cannot be summed as unique customers or outage events.')

"""Teaching explanations and bounded real-data checks added to existing cells.

Original cell identifiers and computations are retained. New IDs are stable so
the rubric matrix and previously saved output can still be traced precisely.
"""
from build_notebooks import md,code

TASK1_GUIDANCE={
1:('Start a Spark session and load the verified prefix artifacts.', 'Use the same scope and UTC policy throughout the notebook.', 'Spark DataFrames are distributed typed tables. Transformations build a lazy plan; count/show trigger actions. This local session uses two worker threads, not a multi-machine cluster.', 'pipeline.make_spark; storage.read_frame; the setup cell below'),
3:('Inspect the original five string columns and actual raw reports.', 'Parsing after inspection preserves invalid tokens and leading-zero county identifiers.', 'read_source supplies a schema and header validation; cache stores reused partitions after an action materializes them.', 'src/gridrescue/pipeline.py: read_source'),
5:('Display a reproducible random selection inside the prefix.', 'A few rows help us recognize the data without collecting the dataset.', 'rand(seed=17) orders this bounded development subset; show returns only ten rows. Random display does not remove prefix selection bias.', 'Spark rand/orderBy in the cell below'),
7:('Compare raw and clean subset sizes with original source inventory.', 'The full-source audit, January prefix and full-year counties answer different questions.', 'count is a Spark action. Inventory is previously verified metadata; displaying the 2022 integrity count does not load its observations.', 'reports/source_manifest.json and reports/sample_manifest.json'),
9:('Inspect schemas, non-null counts and several distinct memory measurements.', 'File bytes, Python RAM and Spark cache allocation are different quantities.', 'count(column) ignores nulls. Only 1,000 rows enter pandas for display/memory measurement; the full Spark data remains distributed.', 'Spark aggregation; psutil; reports/memory_usage.json'),
11:('Name and explain each source column.', 'A customer count is neither energy consumption nor a count of independent outages.', 'Source names are preserved; Silver adds a typed UTC timestamp and numeric count.', 'pipeline.SOURCE and pipeline.clean'),
13:('Summarize outage size and observed date coverage.', 'The prefix cannot support claims about an entire year or national reporting completeness.', 'describe and min/max/groupBy are Spark aggregations over the explicit prefix scope.', 'Spark DataFrame.describe and groupBy/agg'),
15:('Count distinct non-null values in each original column.', 'Identifiers and timestamps naturally have high cardinality; ID magnitude is not a severity feature.', 'countDistinct is an aggregation that reduces rows to compact summary values.', 'Spark countDistinct'),
17:('Separate eligible positives/negatives from incomplete outcomes.', 'Missing future reports cannot be interpreted as negative escalation labels.', 'groupBy counts the audited completeness and class combinations; mean of a binary label is prevalence among labeled rows.', 'pipeline.audit_labels and the fixed target approval'),
19:('Measure missing tokens, invalid records and internal observation gaps.', 'An unknown count or missing county-time row must never become a fabricated zero.', 'isNull flags missing values in existing rows. A county/year ordered window compares neighboring observed timestamps; quarantine stores rejected original tokens and reasons.', 'pipeline.clean; reports/WHAT_CHANGED_IN_DATA.md'),
21:('Reconcile cleaning totals and verify unique retained county-time keys.', 'Removing exact copies differs from resolving contradictory measurements.', 'clean first rejects invalid rows, removes exact valid source duplicates, then quarantines every distinct variant of conflicting keys with an anti-join. The accounting categories are disjoint.', 'src/gridrescue/pipeline.py: clean'),
23:('Compute a Tukey upper fence and inspect actual extreme reports.', 'A rare severe outage can be valid; statistical rarity alone is insufficient for removal.', 'IQR=Q3−Q1 and fence=Q3+1.5×IQR. Spark approximate quantiles have relative rank error 0.001. Plot input is bounded to 1,000 actual rows.', 'Spark approxQuantile; audit outlier policy'),
25:('Compare keeping, capping, removing and visually transforming extremes.', 'Capping or deleting severe observations could erase the phenomenon being studied.', 'log1p changes the display only; original nonnegative integral values stay in Silver and X.', 'NumPy log1p in the cell; pipeline.clean does not clip valid counts'),
27:('Plot one-variable distributions and UTC observation coverage.', 'Describe skew and reporting patterns before comparing variables.', 'Only small grouped results and bounded observations go to the plotting library; row counts describe reporting, not unique customers.', 'Spark groupBy and Matplotlib'),
29:('Compare past/current features across complete-case escalation classes.', 'Look for descriptive associations while exposing the selection rule.', 'Group means and class counts use eligible anchors only. The current count also enters the target threshold, so this relationship is partly definitional.', 'pipeline.audit_labels; Spark grouped means'),
31:('Plot current counts, exact past lags, past change and variability.', 'Related features can encode overlapping information.', 'A seeded 1,000-row display preserves raw pairs. Missing pairs are omitted from each scatter plot, not zero-filled.', 'pipeline.features and bounded scatter plots'),
33:('Calculate a Pearson correlation matrix for numeric feature pairs.', 'Quantify linear association without treating geography IDs as magnitudes.', 'pandas computes only on the already bounded plotting sample. Pairwise missingness changes the rows used for each coefficient.', 'relationships sample from the preceding cell'),
35:('Compare observed rows and outage-size summaries by state.', 'Separate reporting coverage from severity and avoid totals of repeated people.', 'groupBy partitions logical groups; agg reduces each group; orderBy selects compact chart summaries.', 'Spark groupBy/agg/orderBy'),
37:('Summarize verified counts, decisions and limitations.', 'A defensible conclusion must say exactly which population was processed.', 'Reuse measured audit outputs rather than recomputing or inventing full-source results. Release the Spark session after the final checks.', 'reports/windows/{sample,county}/audit.json and scope ledger'),
}

TASK2_GUIDANCE={
1:('Load Task 1 artifacts using the same data/UTC policies.', 'Preparation must start from validated, unique observations.', 'The Windows adapter reads real Parquet into Spark and restores vector columns. Spark remains responsible for every analytical operation.', 'storage.read_frame; pipeline.make_spark'),
3:('List feature meanings, types, creation rules and exclusions.', 'Only information available at anchor time may enter X.', 'The thirteen numeric predictors use current/past values and calendar parts. IDs and all future diagnostics remain metadata; numeric-only X needs no categorical encoder.', 'pipeline.PREDICTORS; reports/FEATURE_DEFINITIONS.md'),
5:('Build the actual past-only Spark feature table.', 'Exact temporal features preserve meaning when reporting is sparse.', 'A rangeBetween(−3600,0) window includes observed points in the past hour; shifted-epoch left joins retrieve exact 15/60-minute lags. Missing matches remain null.', 'src/gridrescue/pipeline.py: features'),
7:('Independently verify the exact one-hour lag.', 'Four previous rows can span more than an hour when observations are absent.', 'A same-county timestamp equality left join must match the stored lag using null-safe equality. count triggers verification.', 'Spark join and eqNullSafe below'),
9:('Define X and audit the approved target y.', 'Outcome eligibility is separate from feature missingness.', 'The future window is (t,t+3h], requiring twelve unique grid-aligned slots and positive current count. Threshold is current+max(200,0.5×current). Future columns never enter X.', 'pipeline.audit_labels; reports/target_approval.json'),
11:('Inspect actual positive, negative, incomplete and boundary traces.', 'See why unknown future observations cannot safely become negatives.', 'Choose bounded examples, list expected quarter-hours and compare actual reports. If a category is absent, say so; do not fabricate it.', 'pipeline.audit_labels; reports/real_trace_checks.json'),
12:('Measure which observations and counties remain eligible.', 'Complete-case selection can favor persistent, well-reported severe outages.', 'Grouped all-versus-eligible severity and coverage expose selection. These are descriptive checks, not training or a change to the cohort.', 'Spark groupBy; reports/target_feasibility.json'),
14:('Reserve chronological train, validation and sealed test periods.', 'Random row splits would mix adjacent, overlapping windows.', 'Filter only labeled development anchors. Assert that every training/validation label horizon stays before the next partition. 2022 remains unmaterialized.', 'pipeline.split_tag and audit_labels split expressions'),
17:('Load or fit training-only median imputation and standardization.', 'Predictors can be missing even when an outcome is complete; validation must not set training statistics.', 'Spark fits Imputer→VectorAssembler→StandardScaler on eligible 2018–2020 rows. Median quantiles use error 0.001; StandardScaler uses corrected sample standard deviation. A constant training feature maps to zero.', 'pipeline.fit_preparation; storage.load_preparation'),
19:('Inspect final predictor rows, dimensions and split sizes.', 'Verify what a later model would actually receive without fitting a classifier.', 'Preparation transforms train and validation using the same training-fitted stages and ordered allowlist.', 'Spark PipelineModel.transform'),
21:('Check imputed columns and vector finiteness/dimensions.', 'A vector containing NaN/inf or the wrong dimension is unsuitable for later learning.', 'Spark exists checks every vector entry; size enforces thirteen positions. Missing y was excluded rather than imputed.', 'pyspark.ml.functions.vector_to_array and Spark higher-order functions'),
23:('Verify saved data and fitted preprocessing separately.', 'An artifact path alone does not prove a usable save/reload.', 'A separate Python process reloads both real scopes and compares saved vectors against reloaded Spark preprocessing, including null-bearing inputs and exact fitted statistics.', 'scripts/verify_persistence.py; reports/persistence_validation.json'),
}

def _new(kind,name,text):
    cell=(code if kind=='code' else md)(text)
    cell['id']=name
    return cell

DISPLAY_SETUP='''
import pandas as pd,inspect
from IPython.display import Code
from pyspark.sql.types import TimestampType
pd.set_option('display.max_rows',20)
pd.set_option('display.max_columns',16)
pd.set_option('display.float_format',lambda value:f'{value:,.3f}')
plt.rcParams.update({'figure.dpi':110,'axes.titlesize':11,'axes.labelsize':10,
                     'axes.spines.top':False,'axes.spines.right':False,'figure.autolayout':True})
def show_table(frame,rows=10,scope=None):
    # Rendering only: keep timestamps explicitly UTC and collect at most rows.
    bounded=frame.limit(rows)
    for field in bounded.schema:
        if isinstance(field.dataType,TimestampType):
            bounded=bounded.withColumn(field.name,F.date_format(field.name,'yyyy-MM-dd HH:mm:ss'))
    display(Markdown(f'*Scope: {scope or SCOPE_LABEL}; up to {rows} displayed rows.*'))
    display(bounded.toPandas())
SCOPE_LABEL=f"Prefix: {audit['counts']['raw']:,} raw rows, 2018–2021"
'''

SCOPE_CODE='''
full_audit=json.loads((ROOT/'reports/full_development_audit.json').read_text())
assert full_audit['status']=='VERIFIED_FULL_DEVELOPMENT_INTEGRITY_ONLY'
full_rows=pd.DataFrame([{key:item[key] for key in ['year','parsed_rows','invalid_rows_any_reason',
    'null_customers_out','off_grid_timestamp','valid_rows_before_deduplication',
    'min_parsed_timestamp_utc','max_parsed_timestamp_utc']} for item in full_audit['files']])
display(full_rows)
county_audit=json.loads((ROOT/'reports/memory/county/audit.json').read_text())
scope_rows=[{'scope':'Complete development sources — integrity audit only','raw_records':int(full_rows.parsed_rows.sum()),
             'invalid_any_reason':int(full_rows.invalid_rows_any_reason.sum()),'Silver_after_dedup':'Not established nationally'},
            {'scope':'January prefixes — cleaning + EDA','raw_records':audit['counts']['raw'],
             'invalid_any_reason':audit['counts']['invalid'],'Silver_after_dedup':audit['counts']['silver']},
            {'scope':'Three counties — full development dates','raw_records':county_audit['counts']['raw'],
             'invalid_any_reason':county_audit['counts']['invalid'],'Silver_after_dedup':county_audit['counts']['silver']}]
display(pd.DataFrame(scope_rows))
parsed_total=sum(item['row_count'] for item in manifest['files'])
display(Markdown(f"**Inventory reconciliation:** {parsed_total:,} parsed data records + {len(manifest['files'])} headers = {parsed_total+len(manifest['files']):,}. This exactly reconciles the supplied total; the source author's counting method was not independently verified. The 2022 number is existing integrity metadata only."))
display(Markdown('**Coverage:** every full source year ends at December 31 00:00 UTC, leaving the rest of that calendar day unobserved. Prefixes cover January only; the fixed counties cover all twelve months. Full-source duplicate, feature and label results have not been computed nationally.'))
'''

QUARANTINE_CODE='''
rejected=quarantine if MODE=='memory' else read_frame(spark,LOCATIONS['quarantine'])
print(SCOPE_LABEL,'— real quarantined records')
show_table(rejected.groupBy('reason').count().orderBy(F.desc('count')))
show_table(rejected.select(*SOURCE,'reason').orderBy('run_start_time','fips_code'),6)
counts=audit['counts']
remaining=counts['raw']
cleaning_ledger=[{'stage':'Original parsed reports','removed':0,'remaining':remaining}]
for key,label in [('invalid','Invalid source reports'),('exact_duplicates_removed','Exact valid duplicate copies'),('conflict_rows','Distinct conflicting-key variants')]:
    remaining-=counts[key]
    cleaning_ledger.append({'stage':label,'removed':counts[key],'remaining':remaining})
cleaning_ledger.append({'stage':'Silver retained','removed':0,'remaining':counts['silver']})
display(pd.DataFrame(cleaning_ledger))
assert remaining==counts['silver']
display(Markdown(f"**Finding:** {counts['invalid']:,} invalid reports are excluded, with original tokens and reasons retained in quarantine. Missing outage counts are unknown measurements; substituting zero would invent restoration and distort both past features and future labels."))
'''

COUNTY_EDA_CODE='''
coverage=pd.DataFrame(county_audit['coverage_by_county_year'])
display(coverage[['fips_code','county','year','observed_anchors','eligible','positive','negative','first','last']])
from gridrescue.dashboard_data import load_scope
county_daily,_=load_scope(ROOT,'county')  # Verified Spark daily aggregates, not raw data.
monthly=county_daily.assign(month=county_daily.date.dt.to_period('M').astype(str)).groupby(['month','county'])[['observations','sum_customer_observations']].sum().reset_index()
monthly['mean_customers_out']=monthly.sum_customer_observations/monthly.observations
fig,axes=plt.subplots(2,1,figsize=(11,6),sharex=True)
monthly.pivot(index='month',columns='county',values='mean_customers_out').plot(ax=axes[0])
monthly.pivot(index='month',columns='county',values='observations').plot(ax=axes[1],legend=False)
axes[0].set(title='Three fixed counties — monthly reported outage size, 2018–2021',ylabel='Mean customers out per observed row')
axes[1].set(ylabel='Observed county-time rows',xlabel='UTC month')
plt.show()
peak=monthly.loc[monthly.mean_customers_out.idxmax()]
display(Markdown(f"**Finding:** the highest observed county/month mean is {peak.mean_customers_out:,.1f} customers out in {peak['county']} during {peak['month']}. These are repeated reports, not unique people or a causal attribution. The lower panel shows the coverage supporting each mean; no missing observations became zeros."))
display(Markdown('**Reading monthly counts:** month length changes the number of possible rows; a lower monthly total alone does not prove a reporting failure. Calendar-based coverage qualification is reported separately.'))
'''

FEATURE_TABLE_CODE='''
feature_specs=[
('customers_out_t','integer count','Reported count at t','Known current severity'),
('lag_15m','numeric, nullable','Same county at exactly t−15m','Recent state'),
('lag_60m','numeric, nullable','Same county at exactly t−60m','One-hour reference'),
('delta_60m','numeric, nullable','customers_out_t − lag_60m','Observed one-hour change'),
('rolling_mean_60m','numeric','Mean of observed [t−60m,t]','Recent severity level'),
('rolling_variance_60m','numeric','Population variance in observed [t−60m,t]','Recent variation'),
('history_slots_60m','integer, 1–5','Count observed [t−60m,t] slots','Expose incomplete history'),
('hour_utc','integer, 0–23','UTC hour of anchor','Time-of-day baseline'),
('weekday_utc','integer, 1–7','Spark Sunday=1 … Saturday=7','Weekly baseline'),
('month_utc','integer, 1–12','UTC calendar month','Seasonal baseline'),
('lag_15m_missing','binary','1 when exact 15m lag is absent','Preserve missingness'),
('lag_60m_missing','binary','1 when exact 60m lag is absent','Preserve missingness'),
('delta_60m_missing','binary','1 when delta is absent','Approved redundant baseline flag')]
display(pd.DataFrame(feature_specs,columns=['X feature in vector order','type','calculation','justification']))
assert [row[0] for row in feature_specs]==PREDICTORS+[c+'_missing' for c in ['lag_15m','lag_60m','delta_60m']]
display(Markdown('**Exclusions:** FIPS/county/state/time identify or order observations but do not enter X. Future maxima/slots, threshold and y are outcome diagnostics. No external customer denominator exists, so no unverified customer ratio was invented. The 60m-lag and delta missing flags are redundant by definition; both remain unchanged as approved.'))
'''

MANUAL_WINDOW_CODE='''
import math
from datetime import datetime,timedelta
county_locations=scope_paths(ROOT,'county','arrow-local' if MODE=='arrow-local' else 'native')
if MODE=='memory':
    county_silver,_,_=clean(read_source(spark,sorted((ROOT/'data/county_coverage').glob('*.csv'))))
    county_gold=features(county_silver)
else:
    county_silver=read_frame(spark,county_locations['silver'])
    county_gold=read_frame(spark,county_locations['gold'])
anchor=(county_gold.filter((F.col('fips_code')=='06037') & (F.year('timestamp')==2020) &
         (F.month('timestamp')==7) & (F.col('history_slots_60m')==5)).orderBy('timestamp')
         .select('fips_code',F.date_format('timestamp','yyyy-MM-dd HH:mm:ss').alias('anchor_utc'),*PREDICTORS).first())
assert anchor is not None,'No qualified real July anchor; do not fabricate a manual example'
anchor_time=F.to_timestamp(F.lit(anchor.anchor_utc))
history=(county_silver.filter((F.col('fips_code')==anchor.fips_code)&
          F.col('timestamp').between(anchor_time-F.expr('INTERVAL 60 MINUTES'),anchor_time))
          .select(F.date_format('timestamp','yyyy-MM-dd HH:mm:ss').alias('timestamp_utc'),'customers_out').orderBy('timestamp_utc'))
history_rows=history.collect()  # At most five actual quarter-hour observations.
display(pd.DataFrame([row.asDict() for row in history_rows]))
lookup={row.timestamp_utc:row.customers_out for row in history_rows}
when=datetime.fromisoformat(anchor.anchor_utc)
lag15=lookup.get(str(when-timedelta(minutes=15))); lag60=lookup.get(str(when-timedelta(minutes=60)))
values=[row.customers_out for row in history_rows]
mean=math.fsum(values)/len(values); variance=math.fsum((v-mean)**2 for v in values)/len(values)
checks=[('current',lookup[str(when)],anchor.customers_out_t),('lag_15m',lag15,anchor.lag_15m),
        ('lag_60m',lag60,anchor.lag_60m),('delta_60m',lookup[str(when)]-lag60,anchor.delta_60m),
        ('rolling_mean_60m',mean,anchor.rolling_mean_60m),('rolling_variance_60m',variance,anchor.rolling_variance_60m),
        ('history_slots_60m',len(values),anchor.history_slots_60m)]
display(pd.DataFrame(checks,columns=['check','manual result','Spark feature']))
assert all(math.isclose(float(manual),float(actual),rel_tol=1e-10,abs_tol=1e-6) for _,manual,actual in checks)
display(Markdown(f"**Manual verification:** Los Angeles at {anchor.anchor_utc} UTC uses exactly the five displayed historical observations. Mean={mean:,.3f}, population variance={variance:,.3f}. The current observation is included; no future value is used."))
missing_example=county_gold.filter('lag_15m IS NULL OR lag_60m IS NULL').orderBy('timestamp','fips_code')
for name in ['lag_15m','lag_60m','delta_60m']:
    missing_example=missing_example.withColumn(name+'_missing',F.col(name).isNull().cast('double'))
show_table(missing_example.select('fips_code','timestamp','customers_out_t','lag_15m','lag_60m','delta_60m',
           'lag_15m_missing','lag_60m_missing','delta_60m_missing'),3,scope='Three counties, all development dates (2018–2021)')
display(Markdown('**Missing-lag interpretation:** null means that exact historical timestamp is absent. A flag records the gap. Later median imputation fills only a predictor position; it does not create an outage report or change y.'))
'''

ELIGIBILITY_CODE='''
stages=[]
for scope,frame in [('Prefix',candidate),('Three counties',read_frame(spark,county_locations['label_audit']) if MODE!='memory' else audit_labels(county_gold))]:
    row=frame.agg(F.count('*').alias('clean'),F.sum((F.col('customers_out_t')>0).cast('long')).alias('positive_current'),
        F.sum(((F.col('customers_out_t')>0)&(F.col('future_slots')==12)).cast('long')).alias('complete_future'),
        F.sum((F.col('candidate_y').isNotNull()&F.col('split').isin('train','validation')).cast('long')).alias('eligible'),
        F.sum((F.col('split')=='purged').cast('long')).alias('purged')).first().asDict()
    stages.append({'scope':scope,**row,'excluded_clean_anchors':row['clean']-row['eligible']})
display(pd.DataFrame(stages))
assert all(row['clean']>=row['positive_current']>=row['complete_future']>=row['eligible'] for row in stages)
display(Markdown('**Eligibility interpretation:** each successive column applies an additional rule; these columns are nested stages, not removal categories to add together. Incomplete future windows are excluded from both classes even if a partial trace crosses the threshold. Boundary purges can be zero in real data because source years end before the final three hours; the boundary behavior is tested synthetically.'))
'''

SCALING_CODE='''
assert preparation is not None
imputer,assembler,scaler=preparation.stages
medians=imputer.surrogateDF.first().asDict()
fitted=pd.DataFrame({'feature':X_COLUMNS,'training median':[medians[c] for c in X_COLUMNS],
                     'mean after imputation':list(scaler.mean),'sample standard deviation':list(scaler.std)})
display(fitted)
small=prepared.filter('lag_15m IS NULL OR lag_60m IS NULL').orderBy('timestamp','fips_code').limit(1)
example=preparation.transform(small).select(*X_COLUMNS,*imputer.getOutputCols(),'scaled_features').first()
assert example is not None,'No missing-history eligible example; report rather than invent one'
comparison=[]
for i,name in enumerate(X_COLUMNS):
    raw_value=example[name]; imputed=example[imputer.getOutputCols()[i]]
    expected=(imputed-scaler.mean[i])/scaler.std[i] if scaler.std[i]!=0 else 0.
    actual=float(example.scaled_features[i])
    assert math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12)
    comparison.append({'feature':name,'raw predictor':raw_value,'imputed predictor':imputed,'scaled predictor':actual})
display(pd.DataFrame(comparison))
display(Markdown('**Read the example:** absent lag/change entries become the displayed training medians; their binary flags stay 1 before standardization. Standardization is (imputed−training mean)/training sample std. Zero-variance training columns map to zero. January-only prefix training cannot establish seasonal effects; full-year county features remain separately qualified.'))
'''

COUNTY_SUMMARY_CODE='''
# Read verified artifacts only: no refit and no source/holdout scan.
county_proof=json.loads((ROOT/'reports/persistence_validation.json').read_text())
assert county_proof['status']=='VERIFIED'
county_paths=scope_paths(ROOT,'county',county_proof['storage_backend'])
county_report=json.loads((county_paths['report']/'audit.json').read_text())
county_saved=json.loads((county_paths['artifacts']/'preparation/preparation.json').read_text())
verified_county=county_proof['scopes']['county']
assert verified_county['original_fitted_statistics_equal']
fit_stats=county_report['preparation_statistics']
names=fit_stats['feature_order']
assert names==X_COLUMNS==county_saved['imputer']['input_cols']
assert fit_stats['medians']==county_saved['imputer']['medians']
assert fit_stats['mean']==county_saved['scaler']['mean'] and fit_stats['sample_std']==county_saved['scaler']['std']
eligible_counts={row['split']:row['count'] for row in county_report['eligible_preparation_counts']}
split_rows=[]
for split in ['train','validation']:
    groups=[r for r in county_report['label_summary'] if r['split']==split and r['candidate_y'] in (0,1)]
    positive=sum(r['count'] for r in groups if r['candidate_y']==1)
    negative=sum(r['count'] for r in groups if r['candidate_y']==0)
    assert positive+negative==eligible_counts[split]==verified_county['split_rows'][split]
    split_rows.append({'split':split,'source years':', '.join(str(y) for y in sorted({r['year'] for r in groups})),
        'eligible rows':positive+negative,'positive':positive,'negative':negative,'positive prevalence':f'{positive/(positive+negative):.2%}'})
display(pd.DataFrame(split_rows))
assert fit_stats['training_rows']==eligible_counts['train']
total_eligible=sum(eligible_counts.values())
assert total_eligible==verified_county['rows']
raw_nulls=county_report['content_roundtrips']['prepared_features']['source_null_counts']
statistics=pd.DataFrame([{'feature':name,'eligible raw nulls':raw_nulls[name],
    'eligible raw null %':f'{raw_nulls[name]/total_eligible:.2%}','training median':fit_stats['medians'][name],
    'training mean':fit_stats['mean'][i],'training sample std':fit_stats['sample_std'][i]} for i,name in enumerate(names)])
display(statistics)
display(Markdown(f"**Three-county cohort only:** {total_eligible:,} eligible development anchors; preprocessing was fitted on {fit_stats['training_rows']:,} training anchors, never on validation. Null counts above cover eligible train + validation predictors before imputation; fitted statistics use training only. {verified_county['rows_exercising_missing_history']:,} eligible rows exercise missing-history handling in the verified reload. No county rows are merged into the January-prefix worked examples."))
display(Markdown('**Artifact sources:** reports/windows/county/audit.json; artifacts/windows/county/preparation/preparation.json; reports/persistence_validation.json. This is a descriptive summary of existing verified preparation, not a reusable preprocessing fit for earlier CV folds. No classifier or 2022 data is accessed.'))
'''

def enrich_notebook(name,cells):
    task1=name=='task1_eda'
    guidance=TASK1_GUIDANCE if task1 else TASK2_GUIDANCE
    prefix='task1' if task1 else 'task2'
    sections=([(2,'understanding','1. Data understanding'),(18,'cleaning','2. Data cleaning'),
               (26,'eda','3. EDA'),(36,'findings','4. Findings')] if task1 else
              [(2,'features','1. Feature engineering'),(8,'splitting','2. Target and splitting'),
               (16,'preprocessing','3. Preprocessing'),(18,'checks','4. Final checks and storage')])
    purposes=({'understanding':'Source schema, inventory and scope','cleaning':'Invalid reports, duplicate rules and outliers',
               'eda':'Distributions, associations and full-year county context','findings':'Measured decisions and limitations'} if task1 else
              {'features':'Thirteen features, exact lags and worked rolling window','splitting':'Target examples, eligibility and chronology',
               'preprocessing':'Training medians, scaling and real before/after values','checks':'Prepared vectors, validation and save/reload'})
    navigation='\n\n| Navigate | Scope and purpose |\n|---|---|\n'+''.join(
        f'| [{label}](#{prefix}-{anchor}) | '+purposes[anchor]+' |\n'
        for _,anchor,label in sections)
    cells[0]['source'].append('\n\nThis submission performs no classifier fitting. Real-data Task 3 remains **PAUSED for user review**. The 2022 modeling holdout is sealed.\n'+navigation)
    cells[0]['source'].append('''
### Read this scope distinction first

| Scope | Which observations? | What is demonstrated here? |
|---|---|---|
| **January-prefix sample** | First 100,000 source reports per development year, 2018–2021; January only, across many counties | Main EDA and step-by-step feature/imputation/scaling examples; debugging, not the approved modeling population |
| **Three-county full-year cohort** | Los Angeles (06037), Miami-Dade (12086), Harris (48201); all available 2018–2021 dates, spanning all months | Separate full-year context, county history example and verified county preparation summary; approved experimental population for later review-gated Task 3 |

These are **different cohorts**, not successive cleaning stages or interchangeable samples. “Full-year” means dates across the year, not complete observation of every quarter-hour. Neither cohort is nationally representative. Full-source audit totals are integrity evidence, not national feature/label processing. Nothing here loads the 2022 modeling holdout.
''')
    if not task1:
        cells[0]['source'].append('\n[Jump to the three-county Task 2 summary](#task2-county-summary). All other preprocessing worked examples below use the January prefix unless explicitly labeled otherwise.\n')
    for index,anchor,_ in sections: cells[index]['source']=[f'<a id="{prefix}-{anchor}"></a>\n']+cells[index]['source']
    extras={}
    def add_after(index,tag,title,explanation,source):
        extras.setdefault(index,[]).extend([_new('markdown',name+'-'+tag+'-notes',title+'\n\n'+explanation),_new('code',name+'-'+tag,source)])
    if task1:
        add_after(7,'scope-ledger','### Source coverage and the scope ledger',
            '**What/why:** reconcile original parsed counts and distinguish the three populations. **How:** read existing measured audit metadata, with no new raw-source scan. **Where:** reports/full_development_audit.json; memory/county/audit.json.',SCOPE_CODE)
        add_after(19,'quarantine','### Invalid examples and exact cleaning ledger',
            '**What/why:** inspect actual invalid reports and account for every removal. **How:** group quarantine reasons, display six original records and subtract disjoint cleaning categories. **Where:** pipeline.clean and the matching persisted quarantine.',QUARANTINE_CODE)
        add_after(21,'clean-source','### Inspect the implemented cleaning rules',
            '**What/why:** expose the actual shared implementation instead of hiding decisions in a function call. **How:** display its source without rerunning it. **Where:** src/gridrescue/pipeline.py: clean.',"display(Code(inspect.getsource(clean),language='python'))")
        add_after(35,'county-context','### Full-year county context: severity and coverage',
            '**What/why:** supplement January-only EDA with all development months for the fixed counties. **How:** aggregate the verified daily export into weighted monthly means and plot counts beside severity. **Where:** reports/dashboard/county/daily.csv; pipeline audit.',COUNTY_EDA_CODE)
    else:
        add_after(3,'feature-dictionary','### The exact thirteen positions in X',
            '**What/why:** show the complete ordered contract. **How:** match the definition table to the implemented predictor allowlist plus the three missing flags. **Where:** pipeline.PREDICTORS and reports/FEATURE_DEFINITIONS.md.',FEATURE_TABLE_CODE)
        add_after(7,'manual-window','### Manually check real county history',
            '**What/why:** verify exact lag joins and past-only rolling statistics using actual Los Angeles reports. **How:** display at most five rows from a complete one-hour history, calculate values independently, then show real missing-lag rows. **Where:** pipeline.features and persisted county Silver/Gold.',MANUAL_WINDOW_CODE)
        add_after(12,'eligibility-stages','### Nested eligibility stages and exclusions',
            '**What/why:** count every outcome eligibility gate in both scopes. **How:** one compact Spark aggregation per scope; no future null is recoded. **Where:** pipeline.audit_labels.',ELIGIBILITY_CODE)
        add_after(17,'scaling-example','### Training statistics and a real before/after example',
            '**What/why:** make fitted imputation and scaling independently checkable. **How:** display the thirteen fitted statistics and transform one eligible row with missing history. **Where:** Spark PipelineModel stages; pipeline.fit_preparation; storage.load_preparation.',SCALING_CODE)
        add_after(17,'county-summary','<a id="task2-county-summary"></a>\n### Three-county Task 2 summary — verified artifacts',
            '**What / why:** show the actual experimental cohort separately from the prefix teaching examples. **How:** read saved audit counts, eligible predictor null counts and training-fitted JSON statistics, and cross-check them against verified reload evidence. **Implementation:** pipeline.fit_preparation; storage.save_preparation; scripts/verify_persistence.py. No refitting or additional Spark scan is needed.',COUNTY_SUMMARY_CODE)
    result=[]
    for index,cell in enumerate(cells):
        if cell['cell_type']=='code':
            what,why,how,where=guidance[index]
            explanation=f'\n\n**What / why:** {what} {why}\n\n**How:** {how}\n\n**Implementation:** `{where}`.'
            if result and result[-1]['cell_type']=='markdown':
                result[-1]['source'].append(explanation)
            else:
                result.append(_new('markdown',cell['id']+'-explanation',explanation))
            source=''.join(cell['source'])
            if index==1: source+='\n'+DISPLAY_SETUP
            if index==1:
                source=source.replace("display({k:audit.get(k) for k in ['scope','execution','counts','invalid_reasons','outliers','splits','eligible_preparation_counts','preparation']})",'')
                source+='''
county_scope_path=ROOT/'reports/memory/county/audit.json' if MODE=='memory' else scope_paths(ROOT,'county','arrow-local' if MODE=='arrow-local' else 'native')['report']/'audit.json'
county_scope_audit=json.loads(county_scope_path.read_text())
display(pd.DataFrame([{'scope':label,'raw reports':item['counts']['raw'],'Silver rows':item['counts']['silver'],
    'eligible preparation rows':sum(r['count'] for r in item['eligible_preparation_counts'])}
    for label,item in [('January prefix — main worked examples',audit),('Three counties — separate full-year cohort',county_scope_audit)]]))
print('The two cohorts are not combined. Current preparation/scaling examples use the prefix unless labeled three-county.')
'''
            # Render existing bounded results as readable HTML tables. Scientific
            # operations and filters are left unchanged.
            if task1 and index==3: source=source.replace('raw.show(5, truncate=False)','show_table(raw,5)')
            if task1 and index==5: source='show_table(raw.orderBy(F.rand(seed=17)),10)\n'
            if task1 and index==7:
                source=source.replace('display(file_rows)','display(pd.DataFrame(file_rows))').replace("print('Subset selection:', sample_manifest)","display(pd.DataFrame(sample_manifest)[['year','rows','method']])")
            if not task1 and index==5:
                source=source.replace("recomputed.select('fips_code','timestamp',*PREDICTORS).orderBy('fips_code','timestamp').show(12,truncate=False)","show_table(recomputed.select('fips_code','timestamp',*PREDICTORS).orderBy('fips_code','timestamp'),6)")
                source=source.replace("recomputed.explain(mode='simple')","display(Code(inspect.getsource(features),language='python'))\nprint('Configured shuffle partitions:',spark.conf.get('spark.sql.shuffle.partitions'),'Actual feature partitions:',recomputed.rdd.getNumPartitions())")
            if not task1 and index==11:
                source=source.replace("'future_slots','future_max','candidate_y','split']","'escalation_threshold','future_slots','future_max','candidate_y','split']")
                source=source.replace("trajectory.orderBy('timestamp').show(13,truncate=False)","show_table(trajectory.select('timestamp','customers_out').orderBy('timestamp'),13)")
            if not task1 and index==23:
                source=source.replace("display({'selected_county_splits':county_audit['eligible_preparation_counts'],'selected_county_coverage':county_audit['coverage_by_county_year']})","display(pd.DataFrame(county_audit['eligible_preparation_counts']))\ndisplay(pd.DataFrame(county_audit['coverage_by_county_year']))")
                source=source.replace("print('No model selected or trained in Task 2. Approved Task 3 experiments are implemented separately.')","print('HARD STOP: no Task 3 training, CV, tuning or 2022 evaluation. User review is required.')")
                source=source.replace('display(persistence)',"display(pd.DataFrame([dict(scope=scope,rows=item['rows'],dimensions=item['vector_dimension'],exact_vector_mismatches=item['exact_vector_mismatches'],fitted_statistics_equal=item.get('original_fitted_statistics_equal'),missing_history_rows=item.get('rows_exercising_missing_history')) for scope,item in persistence.get('scopes',{}).items()]))\nprint('Full schema, null, timestamp and every-value comparison evidence: reports/persistence_validation.json')\nprint('Windows Arrow-local is a storage workaround. Native Hadoop writing remains blocked; no unsafe binary was installed.')")
            if not task1 and index==17:
                source=source.replace("display(preparation.stages[0].surrogateDF.toPandas())","# Display all actual training statistics once in the next worked example.")
                source=source.replace("print('Training scaler mean:',preparation.stages[-1].mean)","")
                source=source.replace("print('Training scaler std:',preparation.stages[-1].std)","")
                source=source.replace("transformed.select('split','fips_code','timestamp','scaled_features').show(5,truncate=False)","# Final vectors are displayed once under Final Data Checks.")
            if not task1 and index==19:
                source=source.replace("prepared.select('split','fips_code','timestamp',*X_COLUMNS,'candidate_y').show(5,truncate=False)","show_table(prepared.select('split','fips_code','timestamp','customers_out_t','lag_15m','lag_60m','lag_15m_missing','lag_60m_missing','candidate_y').orderBy('timestamp','fips_code'),3)")
                source+="\nvector_rows=transformed.orderBy('timestamp','fips_code').select('scaled_features').limit(3).collect()\ndisplay(pd.DataFrame([list(row.scaled_features) for row in vector_rows],columns=X_COLUMNS))\nprint('Rows above are three real 13-position prepared vectors, in the exact feature order.')\n"
            if not task1 and index==21:
                source=source.replace("transformed.agg(*[F.sum((F.col(c).isNull()|F.isnan(c)).cast('long')).alias(c) for c in imputed]).show(truncate=False)","missing_summary=transformed.agg(*([F.sum((F.col(c).isNull()|F.isnan(c)).cast('long')).alias('raw_'+str(i)) for i,c in enumerate(X_COLUMNS)]+[F.sum((F.col(c).isNull()|F.isnan(c)).cast('long')).alias('imputed_'+str(i)) for i,c in enumerate(imputed)])).first().asDict()\n    display(pd.DataFrame([{'feature':name,'eligible raw missing':missing_summary['raw_'+str(i)],'after imputation missing':missing_summary['imputed_'+str(i)]} for i,name in enumerate(X_COLUMNS)]))")
            if task1:
                source=source.replace('plt.show()',"plt.gcf().suptitle(SCOPE_LABEL,fontsize=9,y=1.04); plt.show()")
                if index==23:
                    source=source.replace("axes[1].set_xlabel('Customers out')","axes[0].set_ylabel('Reported customers out'); axes[0].set_xticks([1],['Observed rows']); axes[1].set_title('Outage-size frequency'); axes[1].set_xlabel('Customers out')")
                if index==31:
                    source=source.replace("relationships.plot.scatter(x='customers_out_t',y='lag_60m',alpha=0.3,figsize=(6,4));", "relationships.plot.scatter(x='customers_out_t',y='lag_60m',alpha=0.3,figsize=(6,4)); plt.title('Current severity versus exact one-hour lag'); plt.xlabel('Current customers out'); plt.ylabel('Customers out at t−60m');")
                    source=source.replace("relationships.plot.scatter(x='delta_60m',y='rolling_variance_60m',alpha=0.3,figsize=(6,4));", "relationships.plot.scatter(x='delta_60m',y='rolling_variance_60m',alpha=0.3,figsize=(6,4)); plt.title('Historical change versus variability'); plt.xlabel('One-hour change in customers out'); plt.ylabel('Past-hour population variance (customers²)');")
                if index==25:
                    source=source.replace("plt.xlabel('log1p(reported customers out), visualization only')","plt.title('Display transform of up to 1,000 sampled clean rows'); plt.xlabel('log1p(reported customers out), visualization only')")
                if index==33:
                    source=source.replace('figsize=(6,5)','figsize=(7.5,6)')
                    source=source.replace('Pairwise-complete Pearson correlation; <=1000 sampled rows','Pearson correlation: up to 1,000 sampled clean rows')
                    source=source.replace('plt.tight_layout();','plt.tight_layout(rect=(0,0,1,.92));')
                if index==29:
                    source=source.replace("target_groups = eligible.groupBy('candidate_y')", "target_inputs=eligible\nfor column in ['lag_15m','lag_60m','delta_60m']:\n    target_inputs=target_inputs.withColumn(column+'_missing',F.col(column).isNull().cast('double'))\ntarget_names=PREDICTORS+[c+'_missing' for c in ['lag_15m','lag_60m','delta_60m']]\ntarget_groups = target_inputs.groupBy('candidate_y')")
                    source=source.replace("F.avg('delta_60m').alias('mean_past_change')", "F.avg('delta_60m').alias('mean_past_change'),*[F.avg(c).alias('avg_'+c) for c in target_names]")
                    source=source.replace('target_groups.show()',"show_table(target_groups.select('candidate_y','rows','mean_current','mean_past_change'),2)")
                    source=source.replace('target_plot = target_groups.toPandas()',"target_plot = target_groups.toPandas()\ndisplay(target_plot.set_index('candidate_y')[['avg_'+c for c in target_names]].rename(index={0:'No escalation',1:'Escalation'}).T.rename(index=lambda name:name.removeprefix('avg_')))\nprint('Table: observed feature means by complete-case label; calendar means are descriptive numeric baseline codes.')")
            updated=code(source); updated['id']=cell['id']; cell=updated
        result.append(cell)
        result.extend(extras.get(index,[]))
    # Eliminate stale pre-approval prose without changing the scientific contract.
    for cell in result:
        if cell['cell_type']=='markdown':
            text=''.join(cell['source']).replace('The target remains provisional.','The fixed three-county target has conditional experimental approval.')
            text=text.replace('Development-only candidate associations are descriptive, not approved target evidence or accuracy.','Development-only target associations are descriptive, not model accuracy or operational validation.')
            text=text.replace('This notebook prepares candidate predictors and audits a provisional target.','This notebook prepares the approved predictors and audits the unchanged experimental target.')
            if cell['id']=='task2_preprocessing-015':
                text+='''

**Why refit preprocessing inside each chronological CV fold?** Task 2's saved training fit uses 2018–2020. In a later fold that validates on 2019, only 2018 belongs to that fold's training period. Reusing the Task 2 fit would let 2019 and 2020 influence medians, means and standard deviations before evaluating 2019—even without using y. That leaks validation/future distribution information.

Each fold must therefore start with an unfitted preprocessing-plus-model pipeline, fit learned steps on that fold's earlier training rows, and apply them unchanged to its validation rows. The three-hour purge separately prevents label-horizon overlap across the boundary; it does not solve preprocessing leakage. After choosing a model using development evidence, the final allowed training refit is a separate step. This explanation changes no methodology and runs no CV or classifier.
'''
            cell['source']=text.splitlines(True)
    return result

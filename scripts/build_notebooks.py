"""Synchronize notebook source, preserving unchanged cells and saved evidence."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from inspect import cleandoc

ROOT = Path(__file__).resolve().parents[1]


def md(text):
    # A heading often begins immediately after the opening triple quote, while
    # later lines carry Python source indentation. Ignore that first line when
    # finding the common margin; preserve intentional relative indentation.
    return {'cell_type': 'markdown', 'metadata': {}, 'source': cleandoc(text).strip().splitlines(True)}


def code(text):
    source = dedent(text).strip() + '\n'
    compile(source, '<notebook-cell>', 'exec')
    return {'cell_type': 'code', 'metadata': {}, 'source': source.splitlines(True),
            'execution_count': None, 'outputs': []}


BOOTSTRAP = """
from pathlib import Path
import sys, json, os
ROOT = next((p for p in [Path.cwd(), *Path.cwd().parents]
             if (p / 'src/gridrescue/pipeline.py').exists()), None)
if ROOT is None:
    raise RuntimeError('Open the notebook from the GridRescue repository.')
sys.path.insert(0, str(ROOT / 'src'))
from gridrescue.pipeline import make_spark, read_source, clean, features, audit_labels, fit_preparation, PREDICTORS, SOURCE
from pyspark.sql import functions as F, Window
from gridrescue.storage import read_frame,load_preparation,scope_paths
from IPython.display import display, Markdown
import matplotlib.pyplot as plt
spark = make_spark('GridRescue coursework')
BASE = ROOT / 'artifacts/sample'
SILVER = ROOT / 'data/silver/sample'
GOLD = ROOT / 'data/gold/sample/features'
LABELS = ROOT / 'data/gold/sample/label_audit'
MODE = os.environ.get('GRIDRESCUE_STORAGE_MODE','arrow-local' if os.name=='nt' else 'parquet')
if MODE not in ['memory','parquet','arrow-local']:
    raise ValueError('GRIDRESCUE_STORAGE_MODE must be memory, parquet or arrow-local')
LOCATIONS=scope_paths(ROOT,'sample','arrow-local' if MODE=='arrow-local' else 'native')
BASE=LOCATIONS['artifacts']; SILVER=LOCATIONS['silver']; GOLD=LOCATIONS['gold']; LABELS=LOCATIONS['label_audit']
AUDIT_PATH = ROOT/'reports/memory/sample/audit.json' if MODE=='memory' else LOCATIONS['report']/'audit.json'
required = [AUDIT_PATH] + ([SILVER,GOLD,LABELS] if MODE!='memory' else [])
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise RuntimeError('Run scripts/make_sample.py then scripts/run_pipeline.py first. Missing: ' + ', '.join(missing))
audit = json.loads(AUDIT_PATH.read_text(encoding='utf-8-sig'))
manifest = json.loads((ROOT / 'reports/source_manifest.json').read_text(encoding='utf-8-sig'))
sample_manifest = json.loads((ROOT / 'reports/sample_manifest.json').read_text(encoding='utf-8-sig'))
if MODE=='memory':
    raw = read_source(spark,sorted((ROOT/'data/sample').glob('*.csv'))).cache()
    silver, quarantine, live_counts = clean(raw)
    assert live_counts==audit['counts']
    gold = features(silver).cache()
    labels = audit_labels(gold).cache()
else:
    silver = read_frame(spark,SILVER)
    gold = read_frame(spark,GOLD)
    labels = read_frame(spark,LABELS)
print('Execution mode:',MODE,'; persistence is verified separately by scripts/preflight.py.')
print('SCOPE: first 100,000 actual rows per development year 2018-2021; not representative.')
print('No 2022 records are loaded for EDA, feature selection, label decisions or fitting.')
print('Three-county experimental target conditionally approved; this notebook performs no supervised training.')
print('Spark:', spark.version, 'Timezone:', spark.conf.get('spark.sql.session.timeZone'))
display({k:audit.get(k) for k in ['scope','execution','counts','invalid_reasons','outliers','splits','eligible_preparation_counts','preparation']})
"""


def task1():
    return [
        md("""# Task 1 for ML — Data Preparation & Exploration
        November 17 discussion edition. Outputs below measure a deterministic **development subset**,
        not the full population. Run the pipeline first, then Run All. Original CSVs are preserved.
        The university rubric is transcribed in `docs/requirements/`; reusable transformations live in
        `src/gridrescue/pipeline.py`. Candidate target associations are feasibility evidence, not model results.
        """),
        code(BOOTSTRAP),
        md("""## 01 Data Understanding
        ### Read Data
        Read source tokens as strings before parsing: this preserves leading-zero FIPS and invalid
        measurement tokens. The actual source column is `customers_out`, not the planned name `sum`.
        """),
        code("""
        sample_paths = sorted((ROOT / 'data/sample').glob('eaglei_outages_*.csv'))
        assert sample_paths and all('2022' not in p.name for p in sample_paths)
        raw = read_source(spark, sample_paths).cache()
        raw.printSchema()
        raw.show(5, truncate=False)
        """),
        md("""### Random Sample Data
        A seeded random display within the prefix subset is not a random population sample.
        Prefix truncation creates artificial final-window gaps; conclusions cannot be generalized to all seasons.
        """),
        code("raw.orderBy(F.rand(seed=17)).show(10, truncate=False)"),
        md("""### Size of Data (Shape)
        Distinguish parsed sample rows from full-file physical record counts. The manifest's physical
        counts are independently parsed records. Complete development Spark integrity counts are
        recorded separately in `reports/full_development_audit.json`; full-source deduplication is not claimed.
        """),
        code("""
        print('Parsed raw subset shape:', (raw.count(), len(raw.columns)))
        print('Clean subset shape:', (silver.count(), len(silver.columns)))
        file_rows = [{k: f.get(k) for k in ['path','bytes','physical_data_lines','row_count','status']}
                     for f in manifest['files']]
        display(file_rows)
        print('Subset selection:', sample_manifest)
        """),
        md("""### Information of Data — Types, Non-null Counts, Memory
        Storage bytes, cached Spark blocks, Python-process RSS and a bounded pandas frame measure different
        things. Spark reports allocated cached-block memory for this local executor at this instant; it is not
        peak cluster RAM or the memory required for the entire source. Python RSS excludes the JVM. The small
        pandas frame includes deep object storage, but must not be extrapolated to 122 million records.
        """),
        code("""
        silver.printSchema()
        raw.select(*[F.count(c).alias(c + '_nonnull') for c in raw.columns]).show(truncate=False)
        silver.select(*[F.count(c).alias(c + '_nonnull') for c in silver.columns]).show(truncate=False)
        print('Subset CSV bytes:', sum(p.stat().st_size for p in sample_paths))
        print('Silver Parquet storage bytes:', sum(p.stat().st_size for p in SILVER.rglob('*.parquet')))
        import psutil
        bounded_frame=raw.limit(1000).toPandas()
        cache_info=spark.sparkContext._jsc.sc().getRDDStorageInfo()
        memory={'mode':MODE,'python_driver_rss_bytes':psutil.Process().memory_info().rss,
                'spark_cached_block_bytes':sum(int(info.memSize()) for info in cache_info),
                'spark_cached_disk_bytes':sum(int(info.diskSize()) for info in cache_info),
                'bounded_pandas_rows':len(bounded_frame),
                'bounded_pandas_deep_bytes':int(bounded_frame.memory_usage(index=True,deep=True).sum()),
                'scope':'Instantaneous local cache allocation and Python RSS; not peak JVM/cluster RAM or whole-source memory'}
        (ROOT/'reports/memory_usage.json').write_text(json.dumps(memory,indent=2),encoding='utf-8')
        display(memory)
        """),
        md("""### Check Names of Columns
        `fips_code`: five-character county identifier; `county`/`state`: geographic labels;
        `customers_out`: reported count of customers without electricity, not kWh;
        `run_start_time`: source UTC observation text, parsed to `timestamp` in Silver.
        One row is a county-time report, not one independent outage event.
        """),
        code("print('Source columns:', raw.columns)\nprint('Silver columns:', silver.columns)"),
        md("### Check Description"),
        code("""
        silver.select('customers_out').describe().show()
        silver.agg(F.min('timestamp').alias('earliest'), F.max('timestamp').alias('latest'),
                   F.countDistinct('fips_code').alias('counties'), F.countDistinct('state').alias('states')).show()
        silver.groupBy(F.year('timestamp').alias('year')).agg(F.min('timestamp').alias('first'),
                F.max('timestamp').alias('last'), F.count('*').alias('rows')).orderBy('year').show()
        """),
        md("""### Number of Unique Values
        Count each source column. High cardinality in IDs and timestamps is expected; FIPS magnitude
        has no meaningful numerical relationship with outage severity.
        """),
        code("raw.agg(*[F.countDistinct(c).alias(c) for c in raw.columns]).show(truncate=False)"),
        md("""### Check Balance of Data
        The target remains provisional. Report eligible candidate class counts separately from incomplete
        outcomes. Do not infer negatives from missing observations or interpret this as model validation.
        """),
        code("""
        labels.groupBy('split','candidate_y','label_complete').count().orderBy('split','candidate_y').show(30)
        eligible = labels.filter("candidate_y IS NOT NULL AND split IN ('train','validation')")
        eligible.agg(F.count('*').alias('eligible_candidates'), F.avg('candidate_y').alias('candidate_positive_prevalence')).show()
        print('Conditional scientific approval applies to the fixed three-county experiment; prefix balance is descriptive only.')
        """),
        md("""## 02 Data Cleaning
        ### Missing Values
        Nulls are missing values inside existing records. A missing county-time row is an unobserved
        interval and may represent zero outages or a reporting gap. Never fill absent rows with zero.
        Missing source identity/count/time fields are quarantined, not imputed.
        """),
        code("""
        raw.agg(*[F.sum(F.col(c).isNull().cast('long')).alias(c) for c in raw.columns]).show()
        display({'measured_cleaning_counts': audit.get('counts'), 'source_nulls': audit.get('nulls_raw')})
        w = Window.partitionBy('fips_code',F.year('timestamp')).orderBy('timestamp')
        gaps = (silver.withColumn('previous_timestamp',F.lag('timestamp').over(w))
                .withColumn('elapsed_seconds',F.unix_timestamp('timestamp')-F.unix_timestamp('previous_timestamp'))
                .filter('elapsed_seconds > 900'))
        gaps.groupBy(F.year('timestamp').alias('year')).agg(F.count('*').alias('gap_transitions'),
             F.sum(F.col('elapsed_seconds')/900-1).alias('missing_slots_between_observed_endpoints'),
             F.max('elapsed_seconds').alias('longest_gap_seconds')).orderBy('year').show()
        print('Gap counts are within county/year observed endpoints; cross-year prefix separations are excluded. Prefix-scope limitations still apply.')
        """),
        md("""### Duplicate Rows
        Exact source duplicates are removed once. All variants of conflicting county-time keys are
        quarantined; arbitrary first/mean values could manufacture an outcome. Reconciliation includes
        invalids, removed exact duplicates, conflict rows and retained Silver observations.
        """),
        code("""
        counts = audit['counts']
        display(counts)
        assert counts['raw'] == sum(counts[k] for k in ['invalid','exact_duplicates_removed','conflict_rows','silver'])
        assert silver.groupBy('fips_code','timestamp').count().filter('count > 1').limit(1).count() == 0
        print('Row reconciliation and clean-key uniqueness verified for this actual subset.')
        """),
        md("""### Outlier Detection
        Tukey's IQR rule flags candidates, not errors. Large disasters can produce real extreme counts.
        Quantiles use Spark approximate quantiles with documented relative rank tolerance 0.001.
        """),
        code("""
        q1,q2,q3 = silver.approxQuantile('customers_out',[0.25,0.5,0.75],0.001)
        fence = q3 + 1.5*(q3-q1)
        stats = silver.agg(F.count('*').alias('n'), F.max('customers_out').alias('maximum'),
                 F.sum((F.col('customers_out')>fence).cast('long')).alias('above_IQR_fence')).first().asDict()
        display({'Q1':q1,'median':q2,'Q3':q3,'upper_fence':fence,**stats})
        silver.orderBy(F.desc('customers_out')).show(10, truncate=False)
        plot_rows = silver.orderBy(F.rand(17)).limit(1000).select('customers_out').toPandas()
        fig,axes=plt.subplots(1,2,figsize=(11,3))
        axes[0].boxplot(plot_rows['customers_out']); axes[0].set_title('Actual random subset of up to 1000 rows')
        axes[1].hist(plot_rows['customers_out'],bins=40); axes[1].set_yscale('log')
        axes[1].set_xlabel('Customers out'); axes[1].set_ylabel('Rows (log scale)'); plt.show()
        print(f"Measured subset: {stats['above_IQR_fence']} / {stats['n']} values exceed the IQR fence {fence:g}; flags alone do not prove error.")
        """),
        md("""### Outlier Treatment Techniques
        Keep plausible nonnegative integral reports. Capping/removal could suppress exactly the escalation
        events of interest; log1p is shown as a reversible visualization transform only. No learned cap is
        fitted on validation or 2022. Invalid tokens are handled separately by quarantine.
        """),
        code("""
        import numpy as np
        plt.figure(figsize=(7,3)); plt.hist(np.log1p(plot_rows['customers_out']),bins=40)
        plt.xlabel('log1p(reported customers out), visualization only'); plt.ylabel('Rows'); plt.show()
        print('Treatment comparison: keep = preserves reported severity; cap/remove = loses extremes; log1p = reduces display skew. Raw counts retained.')
        """),
        md("""## 03 Exploratory Data Analysis
        ### 1. Univariate Analysis
        Charts use small aggregates or bounded samples; the full dataset is never collected into pandas.
        """),
        code("""
        hourly = gold.groupBy('hour_utc').agg(F.count('*').alias('observed_rows'),F.avg('customers_out_t').alias('mean_customers_out')).orderBy('hour_utc').toPandas()
        hourly.plot(x='hour_utc',y='observed_rows',kind='bar',legend=False,figsize=(9,3))
        plt.ylabel('Observed subset rows'); plt.title('UTC hour coverage in prefix subset'); plt.show()
        peak = hourly.loc[hourly['observed_rows'].idxmax()]
        print(f"Most represented UTC hour in this subset: {int(peak['hour_utc'])}, {int(peak['observed_rows'])} rows. Prefix selection prevents seasonal inference.")
        """),
        md("""### 2. Feature vs. Target Analysis
        Development-only candidate associations are descriptive, not approved target evidence or accuracy.
        Strict 12-slot completeness selects persistent observed outages and may bias both classes.
        """),
        code("""
        target_groups = eligible.groupBy('candidate_y').agg(F.count('*').alias('rows'),
            F.avg('customers_out_t').alias('mean_current'),F.avg('delta_60m').alias('mean_past_change')).orderBy('candidate_y')
        target_groups.show()
        target_plot = target_groups.toPandas()
        if not target_plot.empty:
            target_plot.plot(x='candidate_y',y='mean_current',kind='bar',legend=False,figsize=(5,3))
            plt.title('Complete-case escalation label vs current outages'); plt.ylabel('Mean customers out'); plt.show()
        print('Class-conditional differences above are measured associations among complete windows; no causal or predictive claim follows.')
        display(Markdown('**Interpretation:** ' + '; '.join(
            f"candidate {int(r.candidate_y)}: {int(r.rows):,} anchors, mean current count {r.mean_current:,.1f}"
            for r in target_groups.collect()) + '. These overlapping retrospective windows are not independent events.'))
        """),
        md("### 3. Feature-to-Feature Analysis"),
        code("""
        relationships = gold.orderBy(F.rand(17)).limit(1000).select('customers_out_t','lag_60m','delta_60m','rolling_variance_60m').toPandas()
        relationships.plot.scatter(x='customers_out_t',y='lag_60m',alpha=0.3,figsize=(6,4)); plt.show()
        relationships.plot.scatter(x='delta_60m',y='rolling_variance_60m',alpha=0.3,figsize=(6,4)); plt.show()
        print('Current and lag values describe persistence; delta and variance can overlap. Missing exact lags remain absent, so plotted pairs exclude those gaps.')
        """),
        md("### 4. Correlation Analysis"),
        code("""
        corr = relationships.corr(numeric_only=True)
        display(corr)
        fig,ax=plt.subplots(figsize=(6,5)); im=ax.imshow(corr,vmin=-1,vmax=1,cmap='coolwarm')
        ax.set_xticks(range(len(corr)),corr.columns,rotation=60,ha='right'); ax.set_yticks(range(len(corr)),corr.index)
        fig.colorbar(im,ax=ax); plt.title('Pairwise-complete Pearson correlation; <=1000 sampled rows'); plt.tight_layout(); plt.show()
        print('Sign gives linear direction; magnitude gives linear strength. Pairwise missingness and skew can distort correlations; FIPS and future outcomes are excluded.')
        r=corr.loc['customers_out_t','lag_60m']
        display(Markdown(f'**Interpretation:** current count versus exact 60-minute lag has sampled Pearson r={r:.3f}. Positive values indicate historical persistence; this sample association is neither a causal effect nor model performance.'))
        """),
        md("### 5. GroupBy / Statistical Summary Analysis"),
        code("""
        state_summary = silver.groupBy('state').agg(F.count('*').alias('observations'),F.avg('customers_out').alias('mean_customers_out'),
            F.max('customers_out').alias('max_customers_out')).orderBy(F.desc('observations'))
        state_summary.show(20,truncate=False)
        state_plot = state_summary.limit(15).toPandas()
        state_plot.plot(x='state',y='observations',kind='bar',legend=False,figsize=(9,3)); plt.ylabel('Observed subset rows'); plt.tight_layout(); plt.show()
        top=state_summary.first()
        print(f"Most represented state in selected prefixes: {top['state']} ({top['observations']} observations). Row totals measure observation coverage, not unique customers or total events.")
        """),
        md("""## 04 Findings and Limitations
        Explain the measured outputs above before making claims. Prefix scope, sparse reporting,
        repeated customers across intervals and candidate-label selection are material limitations.
        """),
        code("""
        print('Measured raw -> invalid / exact duplicates / conflict variants -> silver:', counts)
        print('No absent rows were filled; plausible extremes retained. Exact-time features are in Gold.')
        print('Three-county experiment approved; these prefix associations are not model performance or national evidence.')
        county_audit=json.loads((ROOT/'reports/memory/county/audit.json').read_text(encoding='utf-8'))
        display(Markdown(f"**Scope comparison:** prefixes retain {counts['silver']:,} of {counts['raw']:,} rows. The three fixed counties retain {county_audit['counts']['silver']:,} of {county_audit['counts']['raw']:,} rows over all development years. Their much higher reporting coverage means neither scope estimates population-wide eligibility."))
        print('National full-source deduplication, Gold features and labels have not been computed. This is scoped EDA, not a completed national pipeline.')
        raw.unpersist()
        spark.stop()
        """),
    ]


def task2():
    return [
        md("""# Task 2 for ML — Feature Engineering & Data Preprocessing
        This notebook prepares candidate predictors and audits a provisional target. It selects or trains
        **no prediction model**. It uses the same measured development prefix subset as Task 1.
        The final 2022 test remains untouched for target/feature/tuning decisions.
        """),
        code(BOOTSTRAP),
        md("""## 01 Feature Engineering
        ### Identify Features
        Source identifiers support temporal grouping and audit joins, not numeric predictors.
        Only current/past observations and UTC calendar parts may enter X.
        """),
        code("""
        import pandas as pd
        feature_review = [
            ('fips_code','string ID','excluded from X; retained for grouping','Magnitude has no meaning; avoid county memorization'),
            ('county, state','categorical labels','excluded from X; retained for EDA','No encoding needed for selected numeric-only X'),
            ('run_start_time -> timestamp','UTC time','parsed; excluded from X','Ordering and audit key, not a magnitude predictor'),
            ('customers_out -> customers_out_t','integer count','renamed and selected','Observed at anchor t'),
            ('lag_15m','numeric','created and selected','Same county exactly t-15m; missing otherwise'),
            ('lag_60m','numeric','created and selected','Same county exactly t-60m; not four previous rows'),
            ('delta_60m','numeric','created and selected','Current minus exact t-60m lag'),
            ('rolling_mean_60m','numeric','created and selected','Observed [t-60m,t] only; includes current'),
            ('rolling_variance_60m','numeric','created and selected','Population variance over observed historical interval'),
            ('history_slots_60m','integer','created and selected','Coverage count out of five expected historical slots'),
            ('hour_utc, weekday_utc, month_utc','integer calendar','created and selected','UTC extraction; weekday Spark Sunday=1'),
            ('lag_15m_missing, lag_60m_missing, delta_60m_missing','binary indicators','created and selected','Record predictor missingness before training-median imputation'),
            ('future_slots, future_max, candidate_y, escalation_threshold','audit outcomes','excluded from X','Future information is label audit only'),
            ('county_customer_ratio','numeric candidate','not created','No approved time-valid customer denominator available'),
        ]
        display(pd.DataFrame(feature_review,columns=['feature','type','disposition','reason']))
        """),
        md("""### Create Features
        Recompute exact-timestamp lags and timestamp-based lookbacks from Silver using reusable code.
        Count sparse history rather than pretending a complete history exists. Extraction: UTC parts;
        generation: lags/deltas/rolling statistics; selection: explicit candidate list, no target-based search.
        """),
        code("""
        recomputed = features(silver).cache()
        recomputed.select('fips_code','timestamp',*PREDICTORS).orderBy('fips_code','timestamp').show(12,truncate=False)
        print('Rows before / after feature generation:',silver.count(),recomputed.count())
        assert recomputed.count()==silver.count()
        recomputed.explain(mode='simple')
        """),
        md("""### Review Changes
        The feature table above is the complete disposition record. Verify an exact lag by a timestamp
        equality join; absence remains null. Rolling windows never extend beyond anchor t.
        """),
        code("""
        lag_check = (recomputed.alias('a').join(silver.alias('h'),
             (F.col('a.fips_code')==F.col('h.fips_code')) &
             (F.col('h.timestamp')==F.col('a.timestamp')-F.expr('INTERVAL 60 MINUTES')),'left')
             .select(F.col('a.lag_60m').alias('computed'),F.col('h.customers_out').alias('expected')))
        assert lag_check.filter(~F.col('computed').eqNullSafe(F.col('expected'))).count()==0
        print('Exact 60-minute lag checked against independent timestamp equality join.')
        """),
        md("""## 02 Data Splitting
        ### Define Inputs — X and provisional y
        X contains selected current/past features and calendar parts. Candidate y=1 if the future maximum
        reaches current count + max(200, 50% of current count) within (t,t+3h]. An anchor must have a
        positive observed current outage and all twelve exact quarter-hour future slots for either class.
        Incomplete windows remain unlabeled, even if an observed future value crosses the threshold.
        This conservative audit rule avoids asymmetric completeness selection but selects persistent outages.
        The user conditionally approved this unchanged target for the fixed three-county university experiment.
        """),
        code("""
        candidate = audit_labels(recomputed).cache()
        for c in ['lag_15m','lag_60m','delta_60m']:
            candidate = candidate.withColumn(c+'_missing',F.col(c).isNull().cast('double'))
        X_COLUMNS = PREDICTORS + [c+'_missing' for c in ['lag_15m','lag_60m','delta_60m']]
        print('X:',X_COLUMNS)
        print('Experimental y: candidate_y; three-county target conditionally approved; never imputed.')
        assert not set(X_COLUMNS) & {'candidate_y','future_slots','future_max','escalation_threshold'}
        candidate.groupBy(F.year('timestamp').alias('year'),'split','label_complete','candidate_y').count().orderBy('year','candidate_y').show(40)
        """),
        md("""### Candidate Label Feasibility — Manually Inspectable Examples
        Inspect positive, negative, incomplete and boundary anchors and their full available trajectories.
        If a category is absent in this actual prefix, report absence rather than inventing an example.
        Prefix boundaries are selection artifacts; no approved final-test balance is inferred.
        """),
        code("""
        for name,predicate in [('positive','candidate_y=1'),('negative','candidate_y=0'),
                               ('incomplete','NOT label_complete'),('split_boundary',"split='purged'")]:
            example=(candidate.filter(predicate).orderBy('timestamp','fips_code')
                     .withColumn('timestamp',F.date_format('timestamp','yyyy-MM-dd HH:mm:ss')).first())
            print('CATEGORY:',name)
            if example is None:
                print('No observed example in this selected subset; not fabricated.')
                continue
            print({k:example[k] for k in ['fips_code','timestamp','customers_out_t','future_slots','future_max','candidate_y','split']})
            from datetime import datetime, timedelta
            anchor=datetime.fromisoformat(example['timestamp'])
            anchor_spark=F.to_timestamp(F.lit(example['timestamp']))
            trajectory=silver.filter((F.col('fips_code')==example['fips_code']) &
                       F.col('timestamp').between(anchor_spark,anchor_spark+F.expr('INTERVAL 3 HOURS')))
            trajectory.orderBy('timestamp').show(13,truncate=False)
            actual_times={datetime.fromisoformat(r[0]) for r in trajectory.select(F.date_format('timestamp','yyyy-MM-dd HH:mm:ss')).collect()}
            expected_times=[anchor+timedelta(minutes=15*i) for i in range(1,13)]
            print('Missing expected future slots:',[str(t) for t in expected_times if t not in actual_times])
            observed_with_endpoints=sorted(actual_times | {anchor,anchor+timedelta(hours=3)})
            print('Largest span between observed times/endpoints in minutes:',max(
                ((b-a).total_seconds()/60 for a,b in zip(observed_with_endpoints,observed_with_endpoints[1:])),default=0))
        print('Read reports/LABEL_FEASIBILITY.md for selection bias and scientific blockers.')
        """),
        code("""
        selection = candidate.groupBy(F.year('timestamp').alias('year'),'state').agg(
            F.count('*').alias('observed_anchors'),
            F.sum(F.col('candidate_y').isNotNull().cast('long')).alias('eligible_anchors'),
            F.avg('customers_out_t').alias('mean_current_all'),
            F.avg(F.when(F.col('candidate_y').isNotNull(),F.col('customers_out_t'))).alias('mean_current_eligible'))
        selection.withColumn('eligibility_fraction',F.col('eligible_anchors')/F.col('observed_anchors')).orderBy('year',F.desc('observed_anchors')).show(30,truncate=False)
        candidate.groupBy('fips_code',F.year('timestamp').alias('year')).agg(
            F.count('*').alias('anchors'),F.sum(F.col('candidate_y').isNotNull().cast('long')).alias('eligible')).orderBy('eligible','fips_code').show(15)
        print('Compare eligibility fractions and all-versus-eligible severity to assess selection; sparse counties and prefix edges can be excluded disproportionately.')
        """),
        md("""### Split the Data
        Train: 2018-2020; validation: 2021; held-out final test: 2022. Labels whose horizon reaches a
        partition boundary (2021, 2022 or end of test) are purged. All 2022 labels, scores and feature choices remain
        uninspected during development. A zero test count here means no 2022 rows loaded, not no test data.
        """),
        code("""
        prepared = candidate.filter("candidate_y IS NOT NULL AND split IN ('train','validation')")
        prepared.groupBy('split').agg(F.count('*').alias('eligible_rows'),F.avg('candidate_y').alias('candidate_positive_prevalence')).show()
        assert candidate.filter("split='test'").count()==0
        assert prepared.filter("(split='train' AND timestamp + INTERVAL 3 HOURS >= TIMESTAMP '2021-01-01') OR (split='validation' AND timestamp + INTERVAL 3 HOURS >= TIMESTAMP '2022-01-01')").count()==0
        print('Test materialization: deferred; no 2022 predictors or labels loaded in this notebook.')
        """),
        md("""### Avoid Leakage
        No forward/centered rolling features. Future measurements live only in candidate audit columns,
        not X. Nearby observations are temporally correlated, so random row splitting is inappropriate.
        Learned preprocessing is fitted only on eligible training anchors; in Task 3 it must be refitted
        separately inside each chronological CV fold. No target-based feature selection has been run.
        Adjacent quarter-hour prediction windows can share eleven of twelve future observations;
        rows are dependent, not independent outage events. Boundary purges cover the three-hour
        horizon. Any later CV requires the same time-aware gap and fold-only preprocessing, but no
        CV or classifier fitting is authorized during this notebook review.
        """),
        md("""## 03 Data Preprocessing
        ### Missing Values
        Preserve missingness indicators and impute eligible predictor nulls with training medians only.
        This creates predictor vectors, not missing source outage observations or labels. An entirely
        null training feature is a block requiring a documented decision, not an invented median.
        ### Categorical Encoding
        Selected X is numeric only; state/county/FIPS remain audit metadata. No categorical encoder is
        fitted. If categories are selected later, their encoder must be trained inside each training fold.
        ### Feature Scaling
        Preparation uses Spark median Imputer, VectorAssembler and StandardScaler. Standardization
        uses training mean/std; it differs from unit-norm normalization. Binary missing flags are assembled
        with numeric variables. Trees need not use standardized vectors; no estimator is fitted here.
        """),
        code("""
        prep_path = BASE / 'preparation'
        preparation = fit_preparation(prepared,X_COLUMNS) if MODE=='memory' else load_preparation(prep_path) if prep_path.exists() else None
        if preparation is None:
            print('BLOCKED: fitted preparation artifact absent; inspect pipeline runtime log. No fabricated transformed output.')
        else:
            print('Fitted stages:',[type(stage).__name__ for stage in preparation.stages])
            print('Persistence:', 'NOT SAVED: in-memory execution' if MODE=='memory' else 'Loaded saved artifact')
            display(preparation.stages[0].surrogateDF.toPandas())
            print('Training scaler mean:',preparation.stages[-1].mean)
            print('Training scaler std:',preparation.stages[-1].std)
            transformed=preparation.transform(prepared)
            transformed.select('split','fips_code','timestamp','scaled_features').show(5,truncate=False)
            constant=[name for name,std in zip(X_COLUMNS,preparation.stages[-1].std) if std==0]
            display(Markdown('**Training coverage limitation:** zero-variance training predictors: ' + ', '.join(constant) + '. Prefix training is January-only, so its scaler cannot establish seasonal feature feasibility. The separate county feature audit covers longer date ranges.'))
            if MODE=='memory':
                stats={'mode':MODE,'predictors':X_COLUMNS,'training_rows':prepared.filter("split='train'").count(),
                       'medians':preparation.stages[0].surrogateDF.first().asDict(),
                       'scaler_mean':[float(v) for v in preparation.stages[-1].mean],
                       'scaler_std':[float(v) for v in preparation.stages[-1].std],
                       'constant_training_predictors':constant,'spark_pipeline_saved':False}
                (ROOT/'reports/preparation_memory.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
        """),
        md("""## 04 Final Data Checks
        ### Check Outputs
        Display actual prepared counts and bounded examples. Model fitting is intentionally absent.
        """),
        code("""
        print('Candidate prepared rows:',prepared.count(),'X columns:',len(X_COLUMNS))
        prepared.select('split','fips_code','timestamp',*X_COLUMNS,'candidate_y').show(5,truncate=False)
        if preparation is not None:
            transformed.groupBy('split').count().show()
            print('Vector dimension:',transformed.select('scaled_features').first()[0].size)
        """),
        md("""### Validate Features
        Validate finite imputed values and vector consistency. Raw missing predictors are expected before
        imputation; missing y values are excluded, not filled. Candidate label presence does not authorize training.
        """),
        code("""
        if preparation is not None:
            imputed = preparation.stages[0].getOutputCols()
            transformed.agg(*[F.sum((F.col(c).isNull()|F.isnan(c)).cast('long')).alias(c) for c in imputed]).show(truncate=False)
            bad = transformed.filter(F.expr(' OR '.join(f'`{c}` IS NULL OR isnan(`{c}`)' for c in imputed))).count()
            assert bad==0
            print('All imputed predictor columns pass null/NaN checks for this subset.')
            from pyspark.ml.functions import vector_to_array
            arrays=transformed.select(vector_to_array('scaled_features').alias('x'))
            nonfinite=arrays.filter(F.exists('x',lambda v:v.isNull()|F.isnan(v)|(F.abs(v)==F.lit(float('inf'))))).count()
            bad_dimensions=arrays.filter(F.size('x')!=len(X_COLUMNS)).count()
            assert nonfinite==0 and bad_dimensions==0
            validation={'mode':MODE,'transformed_rows':transformed.count(),'vector_dimension':len(X_COLUMNS),
                        'nonfinite_vectors':nonfinite,'wrong_dimension_vectors':bad_dimensions,
                        'split_rows':{r['split']:r['count'] for r in transformed.groupBy('split').count().collect()},
                        'pipeline_persistence_verified':False if MODE=='memory' else True}
            (ROOT/'reports/preparation_validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
            display(validation)
        print('Input feature list identical for train and validation:',X_COLUMNS)
        """),
        md("""### Save Preparation
        In-memory execution computes all analytical outputs and fits preparation without saving Spark
        artifacts. Parquet execution loads saved preparation. The separate fresh-process persistence
        report compares every persisted vector against the reloaded pipeline output. Presence alone
        is not treated as verification. Scientific approval is limited to the three-county experiment.
        """),
        code("""
        paths={'bronze':LOCATIONS['bronze'],'silver':SILVER,'gold':GOLD,'label_audit':LABELS,
               'prepared_features':BASE/'prepared_features','preparation':BASE/'preparation'}
        for name,p in paths.items():
            print(name, 'PRESENT' if p.exists() else 'ABSENT / BLOCKED', str(p.relative_to(ROOT)))
        persistence_path=ROOT/'reports/persistence_validation.json'
        persistence=json.loads(persistence_path.read_text()) if persistence_path.exists() else {'status':'UNVERIFIED'}
        display(persistence)
        if MODE!='memory':
            assert persistence['status']=='VERIFIED'
        display({'scope':audit.get('scope'),'counts':audit.get('counts'),'splits':audit.get('splits')})
        county_audit=json.loads((ROOT/'reports/memory/county/audit.json').read_text(encoding='utf-8'))
        display({'selected_county_splits':county_audit['eligible_preparation_counts'],'selected_county_coverage':county_audit['coverage_by_county_year']})
        prefix_counts={r['split']:r['count'] for r in audit['eligible_preparation_counts']}
        county_counts={r['split']:r['count'] for r in county_audit['eligible_preparation_counts']}
        display(Markdown(f"**Interpretation:** eligible prefix anchors: {prefix_counts}; selected-county anchors: {county_counts}. These cohorts differ substantially in temporal coverage. 2022 test rows are not materialized here; zero loaded test rows does not mean no test data exists. Preprocessing uses only prefix training rows. This execution mode is {MODE}; separate persistence status: {persistence['status']}."))
        print('Explain-back: where did the lag come from? Which rows got no y? Which years fitted the scaler? Why is 2022 untouched?')
        print('No model selected or trained in Task 2. Approved Task 3 experiments are implemented separately.')
        recomputed.unpersist()
        spark.stop()
        """),
    ]


def main():
    out = ROOT / 'notebooks'
    out.mkdir(exist_ok=True)
    for name, cells in [('task1_eda', task1()), ('task2_preprocessing', task2())]:
        for index, cell in enumerate(cells):
            cell['id'] = f'{name}-{index:03d}'
        from notebook_enrichment import enrich_notebook
        cells=enrich_notebook(name,cells)
        notebook = {'cells': cells, 'metadata': {
            'kernelspec': {'display_name': 'Python 3 (GridRescue)', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python', 'version': '3.12'}}, 'nbformat': 4, 'nbformat_minor': 5}
        path = out / (name + '.ipynb')
        if path.exists():
            previous=json.loads(path.read_text(encoding='utf-8'))
            backup=ROOT/'artifacts/notebook_source_backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')/path.name
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():
                shutil.copy2(path,backup)
            old_by_id={c['id']:c for c in previous['cells']}
            for cell in cells:
                old=old_by_id.get(cell['id'])
                if old and old['source']==cell['source']:
                    cell.update(old)
            notebook['metadata']=previous['metadata']
        path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding='utf-8')
        print(f'{path.name}: {len(cells)} cells; unchanged outputs retained; changed cells require execution')


if __name__ == '__main__':
    main()

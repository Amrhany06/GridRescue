"""Expanded retrospective target audit; never trains or opens 2022 data."""
import calendar
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.pipeline import make_spark,read_source,clean,features,audit_labels
from pyspark.sql import functions as F,Window


def rows(frame):
    return [r.asDict() for r in frame.collect()]


def aggregates():
    return [F.count('*').alias('anchors'),F.count('candidate_y').alias('eligible'),
            F.sum(F.when(F.col('candidate_y')==1,1).otherwise(0)).alias('positive'),
            F.sum(F.when(F.col('candidate_y')==0,1).otherwise(0)).alias('negative'),
            F.sum(F.when(F.col('future_slots')<12,1).otherwise(0)).alias('incomplete_future'),
            F.sum(F.when((F.col('future_slots')==12)&(F.col('customers_out_t')<=0),1).otherwise(0)).alias('complete_nonpositive'),
            F.avg('customers_out_t').alias('mean_current_all'),
            F.avg(F.when(F.col('candidate_y').isNotNull(),F.col('customers_out_t'))).alias('mean_current_eligible'),
            F.avg(F.when(F.col('candidate_y').isNull(),F.col('customers_out_t'))).alias('mean_current_excluded')]


def main():
    spark=make_spark('GridRescue-expanded-target-audit')
    try:
        paths=[ROOT/'data/county_coverage'/f'eaglei_outages_{y}.csv' for y in range(2018,2022)]
        silver,_,counts=clean(read_source(spark,paths))
        prior=json.loads((ROOT/'reports/memory/county/audit.json').read_text(encoding='utf-8'))
        assert counts==prior['counts']
        assert silver.filter(~F.year('timestamp').between(2018,2021)).limit(1).count()==0
        labels=(audit_labels(features(silver)).withColumn('year',F.year('timestamp'))
                .withColumn('month',F.month('timestamp')).cache())
        assert labels.filter((F.col('future_slots')>12)|(F.col('future_slots')<0)).count()==0
        monthly=rows(labels.groupBy('fips_code','county','state','year','month').agg(*aggregates()).orderBy('year','month','fips_code'))
        yearly=rows(labels.groupBy('fips_code','county','state','year').agg(*aggregates()).orderBy('year','fips_code'))
        for r in monthly:
            r['nominal_slots']=calendar.monthrange(r['year'],r['month'])[1]*96
        for r in yearly:
            r['nominal_slots']=(366 if calendar.isleap(r['year']) else 365)*96
        for r in monthly+yearly:
            r['observed_slot_fraction']=r['anchors']/r['nominal_slots']
            r['eligibility_fraction']=r['eligible']/r['anchors']
            r['positive_fraction']=r['positive']/r['eligible'] if r['eligible'] else None
            assert r['anchors']==r['eligible']+r['incomplete_future']+r['complete_nonpositive']
            assert r['eligible']==r['positive']+r['negative']
        for r in yearly:
            r['coverage_qualified']=r['observed_slot_fraction']>=0.90
        bands=(labels.withColumn('severity_band',F.when(F.col('customers_out_t')<10,'1-9')
                 .when(F.col('customers_out_t')<100,'10-99').when(F.col('customers_out_t')<1000,'100-999')
                 .when(F.col('customers_out_t')<10000,'1000-9999').otherwise('10000+')))
        severity=rows(bands.groupBy('severity_band').agg(*aggregates()).orderBy('severity_band'))
        eligible=labels.filter("candidate_y IS NOT NULL AND split IN ('train','validation')")
        w=Window.partitionBy('fips_code','year').orderBy('epoch')
        adjacent=(eligible.withColumn('previous_eligible_epoch',F.lag('epoch').over(w))
                  .withColumn('previous_y',F.lag('candidate_y').over(w)))
        overlap_condition=(F.col('epoch')-F.col('previous_eligible_epoch')<10800)
        overlap=adjacent.agg(F.count('*').alias('eligible_anchors'),
                   F.sum(F.when(overlap_condition,1).otherwise(0)).alias('anchors_overlapping_previous_eligible_window'),
                   F.sum(F.when(overlap_condition&(F.col('candidate_y')==F.col('previous_y')),1).otherwise(0)).alias('same_class_as_overlapping_previous')).first().asDict()
        overlap['overlap_fraction']=overlap['anchors_overlapping_previous_eligible_window']/overlap['eligible_anchors']
        thinned=rows(eligible.filter('epoch % 10800 = 0').groupBy('year').agg(
            F.count('*').alias('anchors'),F.sum('candidate_y').alias('positive')).orderBy('year'))
        for r in thinned:
            r['negative']=r['anchors']-r['positive']
        report={'status':'VERIFIED','completed_utc':datetime.now(timezone.utc).isoformat(),'2022_accessed':False,
                'target_status':'PROVISIONAL_UNAPPROVED; no model trained','counts':counts,
                'population_proposal':'Fixed counties 06037, 12086, 48201; retrospective positive-outage anchors with all 12 future slots; county-year nominal coverage >=90%',
                'coverage_threshold_predeclared':0.90,'county_month_year':monthly,'county_year':yearly,
                'severity_selection':severity,'overlapping_windows':overlap,'fixed_three_hour_cadence_sensitivity':thinned,
                'purged_anchors':labels.filter("split='purged'").count(),
                'cadence_note':'Three-hour cadence is descriptive sensitivity only; not silently substituted for the primary quarter-hour population.'}
        (ROOT/'reports/target_feasibility.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        import pandas as pd
        pd.DataFrame(monthly).to_csv(ROOT/'reports/target_eligibility_monthly.csv',index=False)
        pd.DataFrame(yearly).to_csv(ROOT/'reports/target_eligibility_yearly.csv',index=False)
        qualified=sum(r['coverage_qualified'] for r in yearly)
        minimum_month_positive=min(r['positive'] for r in monthly)
        minimum_month_negative=min(r['negative'] for r in monthly)
        recommendation='CONDITIONAL GO' if qualified==len(yearly) and minimum_month_positive>0 and minimum_month_negative>0 else 'NO-GO pending cohort review'
        decision=f'''# Target decision: {recommendation}

Recommendation only: **approval is still required before training**. The prediction question and numeric threshold are unchanged.

## Exact proposed experiment

- Population: fixed Los Angeles (06037), Miami-Dade (12086), Harris (48201) observations. County-year reporting coverage must meet a predeclared 90% of nominal calendar quarter-hours. {qualified}/{len(yearly)} development county-years meet this criterion, so it removes no development county-years.
- At each reported positive-outage quarter-hour anchor, y=1 if a reported future count reaches current + max(200, 50% of current) within (t,t+3h]. Both classes require all 12 exact future quarter-hours. Incomplete windows remain unknown.
- Training 2018–2020, validation 2021, sealed final test 2022 in the same three predetermined counties. 2022 has not been opened by this audit. No model has been trained.
- The eventual model is a three-county retrospective reported-escalation model, **not nationally representative**, a new-blackout detector, or proof of physical outage absence.

## Actual feasibility evidence

- {counts['raw']:,} source records; {counts['silver']:,} clean anchors; {sum(r['eligible'] for r in yearly):,} eligible anchors.
- All {len(monthly)} county-month-year groups were measured. Minimum positive / negative class counts in a monthly group: **{minimum_month_positive:,} / {minimum_month_negative:,}**.
- County-year reporting coverage ranges **{min(r['observed_slot_fraction'] for r in yearly):.2%}–{max(r['observed_slot_fraction'] for r in yearly):.2%}**. Nominal denominators include unreported December 31 slots; source files end at 00:00 that day.
- **{overlap['overlap_fraction']:.2%}** of eligible anchors have a preceding eligible future window that overlaps. These rows are highly dependent; row count is not independent event count. The three-hour cadence sensitivity is recorded separately, without changing the proposed primary population.
- Monthly/yearly classes, completeness and included-versus-excluded severity are in `target_feasibility.json` and the two eligibility CSVs. Existing 18 independently checked real traces remain in `real_trace_checks.json`.

## Conditions and limitations

Future reporting completeness is unknown at inference time. Strict complete-case labels define a retrospective selected cohort and can favor persistent, well-monitored outages. Coverage qualification is not evidence that missing slots are zero. An approved result must be described conditionally and tested for reporting/severity selection; it cannot be generalized nationally.

Use the same chronological folds for all algorithms, with training label endpoints strictly before validation begins and an embargo of at least three hours. Fit all learned preprocessing only inside each training fold. Reserve 2021 for development validation/model selection. Freeze choices before a single 2022 evaluation. Report overlapping-window dependence and a separate non-overlapping-cadence sensitivity rather than interpreting thousands of adjacent anchors as independent trials.

## Decision requested

Approve or reject the **unchanged three-hour reported-escalation target and this explicit three-county population**. Approval does not authorize a different target, national claims, zero filling, or repeated final-test inspection. Training remains gated until a reply arrives.
'''
        (ROOT/'reports/TARGET_DECISION.md').write_text(decision,encoding='utf-8')
        print(json.dumps({'recommendation':recommendation,'monthly_groups':len(monthly),'qualified_county_years':qualified,'overlap':overlap}),flush=True)
    finally:
        spark.stop()


if __name__=='__main__':
    main()

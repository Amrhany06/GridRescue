"""Measure feature availability/variation in both real scopes; no labels or fit."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gridrescue.pipeline import make_spark, read_source, clean, features, PREDICTORS
from pyspark.sql import functions as F


def main():
    spark = make_spark('GridRescue-feature-coverage')
    report = {}
    try:
        for scope, directory in [('sample','sample'),('county','county_coverage')]:
            raw = read_source(spark, sorted((ROOT / 'data' / directory).glob('*.csv')))
            silver, _, counts = clean(raw)
            expected = json.loads((ROOT / 'reports/memory' / scope / 'audit.json').read_text(encoding='utf-8'))
            assert counts == expected['counts']
            gold = features(silver).cache()
            aggregates = [F.count('*').alias('feature_rows')]
            for name in PREDICTORS:
                aggregates.extend([F.min(name).alias(name+'_min'), F.max(name).alias(name+'_max'),
                                   F.sum(F.col(name).isNull().cast('long')).alias(name+'_missing')])
            summary = gold.agg(*aggregates).first().asDict()
            assert summary['feature_rows'] == counts['silver']
            assert summary['history_slots_60m_min'] >= 1 and summary['history_slots_60m_max'] <= 5
            year = gold.groupBy(F.year('timestamp').alias('year')).agg(
                F.countDistinct('month_utc').alias('observed_months'), F.countDistinct('hour_utc').alias('observed_hours'),
                F.countDistinct('weekday_utc').alias('observed_weekdays'), F.count('*').alias('feature_rows'),
                F.sum(F.col('lag_15m').isNull().cast('long')).alias('missing_exact_15m_lag'),
                F.sum(F.col('lag_60m').isNull().cast('long')).alias('missing_exact_60m_lag')).orderBy('year')
            report[scope] = {'summary':summary,'by_year':[r.asDict() for r in year.collect()],
                             'fit_performed':False, '2022_accessed':False}
            print(scope, json.dumps(report[scope]), flush=True)
            spark.catalog.clearCache()
        (ROOT / 'reports/feature_feasibility.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    finally:
        spark.stop()


if __name__ == '__main__':
    main()

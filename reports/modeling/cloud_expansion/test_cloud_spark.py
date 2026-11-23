"""Small deterministic tests for the actual Spark path. No nationwide input is needed."""
import tempfile
import unittest
from pathlib import Path

from pyspark.sql import functions as F

from cloud_data import HERE, history_features, monthly_coverage, spark_session, verify_fixture
from gridrescue.pipeline import audit_labels, features


class CloudSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (HERE.parents[2] / 'artifacts').mkdir(exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(prefix='cloud-fixture-', dir=HERE.parents[2] / 'artifacts')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.spark = spark_session(Path(cls.tmp.name), '2g', 2)
        cls.spark.conf.set('spark.sql.shuffle.partitions', '4')
        cls.addClassCleanup(cls.spark.stop)

    def test_trusted_windows_sample_matches_all_features_and_exact_keys(self):
        evidence = verify_fixture(self.spark)
        self.assertEqual(evidence['counties'], 20)
        self.assertEqual(evidence['rows'], 82)

    def test_future_spike_flips_label_without_changing_anchor_history(self):
        epoch = 1577836800
        base = (self.spark.range(25).select(F.lit('06037').alias('fips_code'),
                F.to_timestamp(F.from_unixtime(F.lit(epoch) + F.col('id') * 900)).alias('timestamp'),
                F.lit(100).alias('customers_out')))
        anchor = epoch + 12 * 900
        output = []
        for counts in (base, base.withColumn('customers_out', F.when(
                F.unix_timestamp('timestamp') == anchor + 900, 300).otherwise(F.col('customers_out')))):
            old = audit_labels(features(counts)).where(F.col('epoch') == anchor).first().asDict()
            long = history_features(counts).where(F.unix_timestamp('timestamp') == anchor).first().asDict()
            output.append((old, long))
        self.assertEqual([old['candidate_y'] for old, _ in output], [0, 1])
        self.assertEqual([old['future_slots'] for old, _ in output], [12, 12])
        self.assertEqual(output[0][0]['rolling_variance_60m'], output[1][0]['rolling_variance_60m'])
        self.assertEqual(output[0][1], output[1][1])
        self.assertEqual(output[1][1]['lag_180m'], 100)

    def test_coverage_drops_conflicts_and_excludes_new_york(self):
        names = 'fips_code string, county string, state string, customers_out string, run_start_time string'
        raw = self.spark.createDataFrame([('06037', 'Los Angeles', 'California', '5', '2019-01-01 00:00:00'),
                                          ('06037', 'Los Angeles', 'California', '5', '2019-01-01 00:00:00'),
                                          ('06037', 'Los Angeles', 'California', '1', '2019-01-01 00:15:00'),
                                          ('06037', 'Los Angeles', 'California', '2', '2019-01-01 00:15:00'),
                                          ('36001', 'Albany', 'New York', '5', '2019-01-01 00:00:00')], names)
        self.assertEqual([row.asDict() for row in monthly_coverage(raw, 2019).collect()],
                         [{'fips_code': '06037', 'county': 'Los Angeles', 'state': 'California',
                           'month': 1, 'clean': 1, 'year': 2019}])


if __name__ == '__main__':
    unittest.main()

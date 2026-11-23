"""Exercise exact-time historical windows on small, invented observations."""
from datetime import datetime, timezone
import unittest

from history import history_features, validate_silver
from gridrescue.pipeline import make_spark


def stamp(value):
    """Convert a short ISO UTC timestamp to a Spark fixture value."""
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = make_spark('GridRescue history fixtures')
        cls.spark.sparkContext.setLogLevel('ERROR')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def frame(self, records):
        return self.spark.createDataFrame([(code, stamp(t), value) for code, t, value in records],
                                          ['fips_code', 'timestamp', 'customers_out'])

    def test_year_boundary_exact_slots_current_only_and_county_isolation(self):
        rows = [('06037', '2019-12-31T21:00', 10), ('06037', '2019-12-31T22:15', 12),
                ('06037', '2019-12-31T23:30', 20), ('06037', '2020-01-01T00:00', 35),
                ('06037', '2020-01-01T00:15', 5000), ('06073', '2019-12-31T22:00', 9000)]
        result = history_features(self.frame(rows)).where("fips_code = '06037' AND timestamp = '2020-01-01 00:00:00'").first()
        self.assertIsNone(result.lag_120m)
        self.assertEqual((result.lag_120m_missing, result.lag_180m, result.delta_180m), (1, 10, 25))
        self.assertEqual(result.rolling_max_180m, 35)
        self.assertAlmostEqual(result.reporting_coverage_180m, 4 / 13)
        self.assertEqual(result.trend_30m, 0.5)
        self.assertEqual(result.relative_growth_180m, 2.5)

    def test_zero_history_kept_but_undefined_ratio_and_absent_trend_flag(self):
        rows = [('06037', '2020-01-01T00:00', 0), ('06037', '2020-01-01T01:00', 9),
                ('06037', '2020-01-01T03:00', 25)]
        result = history_features(self.frame(rows)).where("timestamp = '2020-01-01 03:00:00'").first()
        self.assertEqual((result.lag_120m, result.lag_180m, result.delta_180m), (9, 0, 25))
        self.assertIsNone(result.relative_growth_180m)
        self.assertEqual((result.trend_30m_missing, result.relative_growth_180m_missing), (1, 1))

    def test_off_grid_negative_duplicate_and_out_of_period_anchor_rejected(self):
        for rows in ([('06037', '2020-01-01T01:02', 5)], [('06037', '2020-01-01T01:00:00.250', 5)],
                     [('06037', '2020-01-01T01:00', -1)],
                     [('06037', '2020-01-01T01:00', 8)] * 2, [('06037', '2022-01-01T01:00', 5)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_silver(self.frame(rows), ['06037'])

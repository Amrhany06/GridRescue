import unittest
from datetime import datetime, timedelta
from gridrescue.pipeline import clean, features, audit_labels, split_tag, fit_preparation, make_spark


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = make_spark('GridRescue-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def raw(self, rows):
        return self.spark.createDataFrame(rows, 'fips_code string, county string, state string, customers_out string, run_start_time string')

    def test_clean_preserves_fips_quarantines_conflicts_and_reconciles(self):
        rows = [('01001','A','S','10','2020-01-01 00:00:00')]*2
        rows += [('01001','A','S',v,'2020-01-01 00:15:00') for v in ['20','21']]
        rows += [('01001','A','S','-1','2020-01-01 00:30:00'), ('01001','A','S',None,'2020-01-01 00:45:00')]
        silver, rejected, stats = clean(self.raw(rows))
        self.assertEqual(silver.first().fips_code, '01001')
        self.assertEqual(stats, dict(raw=6, invalid=2, exact_duplicates_removed=1, conflict_rows=2, silver=1))
        self.assertEqual(rejected.count(), 4)

    def test_lags_match_timestamp_not_previous_row_and_features_ignore_future(self):
        rows = [('01001','A','S',v,t) for v,t in [('10','2020-01-01 00:00:00'),('30','2020-01-01 00:30:00'),('999','2020-01-01 02:00:00')]]
        df,_,_ = clean(self.raw(rows))
        out=features(df).orderBy('timestamp').collect()
        self.assertIsNone(out[1].lag_15m)
        self.assertIsNone(out[1].lag_60m)
        self.assertEqual(out[1].rolling_mean_60m,20)
        self.assertEqual(out[1].history_slots_60m,2)

    def test_labels_require_all_twelve_slots_and_purge_boundary(self):
        start=datetime(2020,12,31,20)
        rows=[('01001','A','S',str(400 if i==4 else 100),(start+timedelta(minutes=15*i)).strftime('%Y-%m-%d %H:%M:%S')) for i in range(18)]
        df,_,_=clean(self.raw(rows))
        out=audit_labels(features(df)).orderBy('timestamp').collect()
        self.assertEqual(out[0].candidate_y,1)
        self.assertEqual(out[4].candidate_y,0)
        self.assertIsNone(out[8].candidate_y)
        self.assertEqual(out[8].split,'purged')
        gap=df.filter("timestamp != '2020-12-31 21:00:00'")
        self.assertIsNone(audit_labels(features(gap)).orderBy('timestamp').first().candidate_y)

    def test_split_uses_horizon_and_test_is_sealed(self):
        self.assertEqual(split_tag(datetime(2019,12,31,23)), 'train')
        self.assertEqual(split_tag(datetime(2020,12,31,22)), 'purged')
        self.assertEqual(split_tag(datetime(2021,1,1)), 'validation')
        self.assertEqual(split_tag(datetime(2022,1,1)), 'test')

    def test_bad_tokens_are_quarantined_without_parser_crash(self):
        rows=[('1001','A','S','1','2020-01-01 00:00:00'),
              ('01001','A','S','1.5','2020-01-01 00:00:00'),
              ('01001','A','S','999999999999999999999999','2020-01-01 00:00:00'),
              ('01001','A','S','1','2020-01-01 00:01:00'),
              ('01001','A','S','1','2020-01-01 00:00:00junk')]
        good,bad,stats=clean(self.raw(rows))
        self.assertEqual(stats['invalid'],5)
        self.assertEqual(good.count(),0)
        self.assertEqual(bad.count(),5)
        bad_timestamp=bad.filter("run_start_time LIKE '%junk'").first()
        self.assertIn('invalid_timestamp',bad_timestamp.reason)
        self.assertNotIn('off_grid_timestamp',bad_timestamp.reason)

    def test_other_county_and_later_measurement_cannot_change_anchor_features(self):
        from gridrescue.pipeline import PREDICTORS
        prefix=[('01001','A','S','10','2020-01-01 00:00:00'),
                ('01001','A','S','20','2020-01-01 00:15:00')]
        extra=[('01003','B','S','9999','2020-01-01 00:00:00'),
               ('01001','A','S','8888','2020-01-01 00:30:00')]
        before,_,_=clean(self.raw(prefix))
        after,_,_=clean(self.raw(prefix+extra))
        left=features(before).filter("timestamp='2020-01-01 00:15:00'").select(*PREDICTORS).first()
        right=features(after).filter("fips_code='01001' AND timestamp='2020-01-01 00:15:00'").select(*PREDICTORS).first()
        self.assertEqual(left,right)

    def test_preparation_rejects_all_missing_training_and_no_train(self):
        import tempfile
        df=self.spark.createDataFrame([('train',None),('validation',10.0)],'split string, x double')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'All-null training feature'):
                fit_preparation(df,['x'],d+'/prep')
            with self.assertRaisesRegex(ValueError,'No training rows'):
                fit_preparation(df.filter("split='validation'"),['x'],d+'/prep')

    def test_preparation_fits_only_training_and_saves_reload(self):
        import tempfile
        from pyspark.ml import PipelineModel
        df=self.spark.createDataFrame([('train',1.0),('train',3.0),('validation',999.0)],'split string, x double')
        # Verify train-only fitting independently of the storage integration.
        in_memory=fit_preparation(df,['x'])
        self.assertEqual(list(in_memory.stages[-1].mean),[2.0])
        self.assertEqual(in_memory.transform(df).count(),3)
        with tempfile.TemporaryDirectory() as d:
            model=fit_preparation(df,['x'],d+'/prep')
            self.assertEqual(list(model.stages[-1].mean),[2.0])
            loaded=PipelineModel.load(d+'/prep')
            self.assertEqual(loaded.transform(df).count(),3)


if __name__=='__main__':
    unittest.main()

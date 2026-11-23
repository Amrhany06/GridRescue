"""Exercise the real Streamlit app and reconcile displayed data with exports."""
import unittest
from datetime import date
from pathlib import Path
import pandas as pd
import pyarrow as pa
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def app(self):
        app=AppTest.from_file(str(ROOT/'app/dashboard.py'),default_timeout=30).run()
        self.assertEqual(len(app.exception),0)
        return app

    def test_default_verified_county_scope_reconciles_kpis(self):
        app=self.app()
        self.assertEqual(len(app.metric),4)
        self.assertEqual(app.metric[0].value,'416,940')
        self.assertEqual(app.metric[1].value,'4,383')
        self.assertEqual(app.metric[2].value,'455,986')
        self.assertTrue(any('not live' in c.value.lower() for c in app.caption))

    def test_geography_date_and_severity_filters_match_export(self):
        app=self.app()
        app.multiselect[0].set_value(['California']).run()
        self.assertEqual(app.metric[0].value,'138,885')
        app.multiselect[1].set_value(['Los Angeles, California']).run()
        app.date_input[0].set_value((date(2020,6,1),date(2020,6,30))).run()
        app.number_input[0].set_value(1000).run()
        self.assertEqual(len(app.exception),0)
        source=pd.read_csv(ROOT/'reports/memory/county/dashboard_daily.csv',parse_dates=['date'])
        expected=source[(source.state=='California') & (source.county=='Los Angeles') &
                        source.date.between('2020-06-01','2020-06-30') & (source.peak_customers_out>=1000)]
        self.assertGreater(len(expected),0)
        actual=app.dataframe[-1].value
        self.assertEqual(int(actual.observations.sum()),int(expected.observations.sum()))
        self.assertEqual(len(actual),len(expected))
        self.assertEqual(app.metric[0].value,f'{int(expected.observations.sum()):,}')
        charts=app.get('vega_lite_chart')
        self.assertEqual(len(charts),3)
        mean_data=pa.ipc.open_stream(charts[0].proto.datasets[0].data.data).read_all().to_pandas()
        coverage=pa.ipc.open_stream(charts[1].proto.datasets[0].data.data).read_all().to_pandas()
        expected_daily=expected.groupby('date')[['observations','sum_customer_observations']].sum().sort_index()
        self.assertEqual(int(coverage.observations.sum()),int(expected.observations.sum()))
        expected_means=(expected_daily.sum_customer_observations/expected_daily.observations).tolist()
        self.assertEqual(len(mean_data),len(expected_means))
        for actual_mean,expected_mean in zip(mean_data.mean_customers_out,expected_means):
            self.assertAlmostEqual(actual_mean,expected_mean)

    def test_empty_severity_result_is_explicit_and_does_not_crash(self):
        app=self.app()
        app.number_input[0].set_value(1000000000).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.metric),0)
        self.assertTrue(any('No observations' in c.value for c in app.info))

    def test_scope_switch_and_dependent_county_selection_remain_valid(self):
        app=self.app()
        app.multiselect[0].set_value(['California']).run()
        app.multiselect[1].set_value(['Los Angeles, California']).run()
        app.multiselect[0].set_value(['Texas']).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.multiselect[1].value,[])
        app.selectbox[0].select('January prefix (debugging subset)').run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.metric[0].value,'333,631')

    def test_independent_cities_keep_distinct_fips_identities(self):
        app=self.app()
        app.selectbox[0].select('January prefix (debugging subset)').run()
        app.multiselect[0].set_value(['Maryland']).run()
        options=app.multiselect[1].options
        self.assertIn('Baltimore [24005], Maryland',options)
        self.assertIn('Baltimore [24510], Maryland',options)
        app.multiselect[1].set_value(['Baltimore [24510], Maryland']).run()
        detail=app.dataframe[-1].value
        self.assertEqual(set(detail.fips_code),{'24510'})
        self.assertTrue(detail.observations.between(1,96).all())

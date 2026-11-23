"""Focused checks for the isolated expansion."""
import unittest

from prepare_cohort import ORIGINAL, STATE_ORDER, select_counties


class SelectionTests(unittest.TestCase):
    def test_balanced_selection_keeps_originals_and_freezes_spatial_holdouts(self):
        rows = []
        for state, prefix in list(STATE_ORDER.items())[:5]:
            codes = [f'{prefix}{index:03}' for index in range(1, 6)]
            if state in ORIGINAL:
                codes[4] = ORIGINAL[state]
            for code in codes:
                for year in range(2018, 2022):
                    for month in range(1, 13):
                        from calendar import monthrange
                        rows.append({'fips_code': code, 'county': code, 'state': state, 'year': year,
                                     'month': month, 'clean': monthrange(year, month)[1] * 96})
        selected, _, attempts = select_counties(rows)
        self.assertEqual(selected, select_counties(list(reversed(rows)))[0])
        self.assertEqual(attempts[-1]['annual'], 0.90)
        self.assertEqual(len(selected), 20)
        self.assertEqual(sum(item['role'] == 'seen' for item in selected), 12)
        self.assertEqual(sum(item['role'] == 'unseen_county' for item in selected), 4)
        self.assertEqual({x['state'] for x in selected if x['role'] == 'unseen_state'}, {'New York'})
        self.assertTrue(set(ORIGINAL.values()) <= {x['fips_code'] for x in selected if x['role'] == 'seen'})

    def test_monthly_discontinuity_is_excluded_even_with_high_annual_coverage(self):
        from calendar import monthrange
        from prepare_cohort import qualify_counties
        rows = [{'fips_code': '06037', 'county': 'Los Angeles', 'state': 'California', 'year': year,
                 'month': month, 'clean': (1 if year == 2020 and month == 12 else monthrange(year, month)[1] * 96)}
                for year in range(2018, 2022) for month in range(1, 13)]
        self.assertEqual(qualify_counties(rows), [])

    def test_coverage_fallback_uses_strictest_feasible_common_tier(self):
        from calendar import monthrange
        rows = []
        for state, prefix in list(STATE_ORDER.items())[:5]:
            codes = [ORIGINAL.get(state, f'{prefix}001'), *[f'{prefix}{i:03}' for i in (2, 3, 4)]]
            for code in codes:
                for year in range(2018, 2022):
                    for month in range(1, 13):
                        rows.append({'fips_code': code, 'county': code, 'state': state, 'year': year,
                                     'month': month, 'clean': int(monthrange(year, month)[1] * 96 * .72)})
        selected, _, attempts = select_counties(rows)
        self.assertEqual(len(selected), 20)
        self.assertEqual([item['annual'] for item in attempts], [.90, .75, .65])


class ModelingTests(unittest.TestCase):
    def test_two_geography_blocks_encode_unseen_state_and_county_independently(self):
        import numpy as np
        import pandas as pd
        from train_cohort import FEATURE_COLUMNS, make_variant
        base = pd.DataFrame({name: [1., 2., 3., 4.] for name in FEATURE_COLUMNS})
        base['state'] = ['California', 'California', 'Florida', 'Florida']
        base['fips_code'] = ['06037', '06037', '12086', '12086']
        model = make_variant('both').fit(base, [0, 1, 0, 1])
        new = base.iloc[:2].assign(state=['California', 'New York'], fips_code=['06059', '36061'])
        transformed = model.named_steps['prepare'].transform(new)
        np.testing.assert_array_equal(transformed[:, -4:], [[1., 0., 0., 0.], [0., 0., 0., 0.]])

"""Fixture checks. These tests never request Figshare data or fit a booster."""
import hashlib
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from cloud_data import NUMERIC, training_parity_sample, verify_tier_a_features
from cloud_train import preprocessing_snapshot, verify_preprocessing
from train_local import model_for

from cloud_core import (checkpoint, download_file, inspect_source, select_tiers,
                        validate_training_counties)
from cloud_data import fingerprint, read_rows, exact_period
from cloud_train import flag_workload, fold_bounds, recall_cutoffs


class Response:
    def __init__(self, status, body, content_range=None):
        self.status_code = status
        self.body = body
        self.headers = {'Content-Range': content_range} if content_range else {}
        self.url = 'https://figshare.com/file'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(self.status_code)

    def iter_content(self, chunk_size):
        yield self.body


class CloudTests(unittest.TestCase):
    def test_real_checkpoint_feature_gate_rejects_value_and_null_mask_changes(self):
        frame = pd.DataFrame({name: [3., 8., 1005.] for name in NUMERIC})
        frame = frame.assign(fips_code=['06037', '06037', '12086'], state=['California'] * 2 + ['Florida'],
                             timestamp=pd.date_range('2020-01-01', periods=3, freq='15min', tz='UTC'),
                             candidate_y=[0, 1, 0], hour_utc=[0, 0, 0], future_slots=12,
                             reporting_coverage_180m=[.9, 1., 1.], lag_15m=[np.nan, 3., 8.])
        sample = training_parity_sample(frame.iloc[::-1])
        self.assertEqual(sample.index.tolist(), [0, 1, 2])
        verify_tier_a_features(frame, sample, 'train')
        for value in (4., np.nan):
            modified = frame.copy()
            modified.loc[1, 'lag_15m'] = value
            with self.assertRaises(AssertionError):
                verify_tier_a_features(modified, sample, 'train')

    def test_preprocessing_gate_checks_transforms_and_unseen_state(self):
        model = model_for('rf_history_state', None)
        train = pd.DataFrame({name: [1., 3., np.nan] for name in NUMERIC}).assign(state='California')
        sample = train.assign(state=['California', 'New York', 'California'])
        model.named_steps['prepare'].fit(train)
        expected = preprocessing_snapshot(model, sample)
        self.assertEqual(expected['transformed'][1][-1], 0.)
        verify_preprocessing(model, sample, expected)
        modified = train.copy()
        modified[NUMERIC] = modified[NUMERIC].fillna(15) + 1
        model.named_steps['prepare'].fit(modified)
        with self.assertRaises(AssertionError):
            verify_preprocessing(model, sample, expected)

    def test_resume_accepts_correct_range_and_publishes_verified_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'data.csv'
            target.with_suffix('.csv.partial').write_bytes(b'abc')
            expected = dict(size=6, md5=hashlib.md5(b'abcdef').hexdigest(), sha256=hashlib.sha256(b'abcdef').hexdigest())
            seen = []

            def get(url, **kwargs):
                seen.append(kwargs['headers'].get('Range'))
                return Response(206, b'def', 'bytes 3-5/6')

            download_file('https://figshare.com/file', target, expected, get=get)
            self.assertEqual(seen, ['bytes=3-'])
            self.assertEqual(target.read_bytes(), b'abcdef')
            self.assertFalse(target.with_suffix('.csv.partial').exists())

    def test_ignored_range_restarts_and_bad_checksum_stays_unpublished(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'data.csv'
            target.with_suffix('.csv.partial').write_bytes(b'abc')
            expected = dict(size=6, md5='0' * 32, sha256='0' * 64)
            with self.assertRaisesRegex(ValueError, 'checksum'):
                download_file('https://figshare.com/file', target, expected, get=lambda *a, **k: Response(200, b'abcdef'))
            self.assertFalse(target.exists())
            self.assertEqual(target.with_suffix('.csv.partial').read_bytes(), b'abcdef')

    def test_mismatched_content_range_is_rejected_without_appending(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'data.csv'
            partial = target.with_suffix('.csv.partial')
            partial.write_bytes(b'abc')
            expected = dict(size=6, md5='0' * 32, sha256='0' * 64)
            with self.assertRaisesRegex(ValueError, 'Content-Range'):
                download_file('https://figshare.com/file', target, expected,
                              get=lambda *a, **k: Response(206, b'ef', 'bytes 4-5/6'))
            self.assertEqual(partial.read_bytes(), b'abc')

    def test_source_validation_ignores_unapproved_year_and_rejects_metadata_drift(self):
        pins = {'article_id': 1, 'version': 4, 'files': [dict(year=y, id=y, name=f'eaglei_outages_{y}.csv',
                 size=10, md5='a'*32) for y in range(2018, 2022)]}
        files = [dict(id=r['id'], name=r['name'], size=r['size'], computed_md5=r['md5'],
                      downloadUrl=f'https://figshare.com/ndownloader/files/{r["id"]}') for r in pins['files']]
        files.append(dict(id=2022, name='eaglei_outages_2022.csv', size=30))
        meta = {'id': 1, 'version': 4, 'files': files}
        self.assertEqual(set(inspect_source(meta, pins)), {2018, 2019, 2020, 2021})
        meta['files'][0]['size'] = 99
        with self.assertRaisesRegex(ValueError, 'differs'):
            inspect_source(meta, pins)

    def test_training_excludes_all_held_out_counties_and_new_york(self):
        validate_training_counties(['06037', '48001'], ['06071'])
        for bad in (['06071'], ['36001'], ['6037'], ['06037', '06037']):
            with self.assertRaises(ValueError):
                validate_training_counties(bad, ['06071'])

    def test_nested_county_tiers_respect_the_cap_and_leave_rows_unduplicated(self):
        tiers = select_tiers({'06037': 1_053_328}, [('48001', 1_850_000), ('12001', 200_000),
                                                ('42001', 4_850_000), ('17001', 200_000)], ['06071'])
        self.assertEqual(tiers['A']['rows'], 1_053_328)
        self.assertEqual(tiers['B']['counties'], ['06037', '48001'])
        self.assertEqual(tiers['C']['counties'], ['06037', '48001', '12001', '42001'])
        self.assertEqual(tiers['C']['rows'], 7_953_328)

    def test_fingerprint_is_order_independent_but_preserves_labels_and_exact_identity(self):
        frame = pd.DataFrame({'fips_code': ['06003', '06001'], 'timestamp': pd.to_datetime(
            ['2021-01-01T00:00Z', '2021-01-01T00:15Z'], utc=True), 'candidate_y': [1, 0]})
        self.assertEqual(fingerprint(frame), fingerprint(frame.iloc[::-1]))
        self.assertNotEqual(fingerprint(frame), fingerprint(frame.assign(candidate_y=[0, 1])))
        with self.assertRaises(ValueError):
            fingerprint(pd.concat([frame, frame.iloc[:1]]))
        with self.assertRaises(ValueError):
            fingerprint(frame.assign(candidate_y=[1, np.nan]))
        with self.assertRaises(ValueError):
            fingerprint(frame.assign(timestamp=frame.timestamp + pd.DateOffset(microseconds=1)))

    def test_training_fold_drops_exactly_the_boundary_and_selects_counties_first(self):
        frame = pd.DataFrame({'fips_code': ['06037', '06037', '06037', '06071'], 'timestamp': pd.to_datetime(
            ['2018-06-30T20:45Z', '2018-06-30T21:00Z', '2018-07-01T00:00Z', '2018-06-30T20:45Z'], utc=True),
            'candidate_y': [0, 1, 1, 0]})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            frame.to_parquet(path/'part-00000.parquet', index=False)
            *_, fit_end, _ = fold_bounds([('2018_H2','2018-07-01','2019-01-01')], '2018_H2')
            result = read_rows([path], ['06037'], ['fips_code','timestamp','candidate_y'], end=fit_end)
            self.assertEqual(result.candidate_y.tolist(), [0])
            anchors = read_rows([path], ['06037'], ['fips_code','timestamp','candidate_y'], timestamps=frame.timestamp.iloc[1:2])
            self.assertEqual(anchors.timestamp.tolist(), frame.timestamp.iloc[1:2].tolist())
            exact_period(result, '2018-01-01', '2018-07-01')
            with self.assertRaises(ValueError):
                exact_period(frame, '2018-01-01', '2018-07-01')

    def test_recall_cutoffs_preserve_float32_ties_with_strict_decisions(self):
        y = np.array([1, 1, 0, 1, 0, 1])
        scores = np.array([.75, .5, .5, .25, .25, .125], dtype='float32')
        frozen = recall_cutoffs(y, scores, [40, 50, 60])
        self.assertEqual(frozen['target_40'], np.nextafter(.5, -np.inf))
        self.assertEqual(frozen['target_50'], frozen['target_40'])
        self.assertEqual(int(y[scores.astype(float) > frozen['target_60']].sum()), 3)

    def test_flag_run_breaks_on_gap_and_county_change(self):
        frame = pd.DataFrame({'fips_code': ['06037', '06037', '06037', '06071'], 'timestamp': pd.to_datetime(
            ['2021-01-01T00:00Z','2021-01-01T00:15Z','2021-01-01T00:45Z','2021-01-01T01:00Z'], utc=True),
            'candidate_y': [0, 1, 0, 0]})
        self.assertEqual(flag_workload(frame, np.ones(4, dtype=bool)),
                         {'flagged_rows': 4, 'flag_runs': 3, 'runs_all_rows_negative': 2})

    def test_checkpoint_restores_without_building_and_detects_damage(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            drive = root / 'drive'
            first = checkpoint(root/'vm1', drive, 'fixture', lambda out: (out/'data.txt').write_text('saved'))
            self.assertEqual((first/'data.txt').read_text(), 'saved')
            restored = checkpoint(root/'vm2', drive, 'fixture', lambda _: self.fail('recomputed'))
            self.assertEqual((restored/'data.txt').read_text(), 'saved')
            saved = drive/'fixture.zip'
            saved.write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                checkpoint(root/'vm3', drive, 'fixture', lambda _: self.fail('recomputed'))


if __name__ == '__main__':
    unittest.main()

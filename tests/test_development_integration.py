"""The development loader must consume only verified county storage."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gridrescue.experiment import fingerprint
from gridrescue.modeling import FEATURE_COLUMNS


class DevelopmentSourceTests(unittest.TestCase):
    def test_frozen_pipeline_reloads_in_fresh_process_without_holdout(self):
        from gridrescue.inference import freeze_pipeline, verify_development_reload

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            frame = pd.DataFrame({name: [0., 1., 2., 3.] for name in FEATURE_COLUMNS})
            frame['candidate_y'] = [0, 0, 1, 1]
            frame['split'] = ['train', 'train', 'validation', 'validation']
            selection = {'frozen': True, 'model': 'Logistic Regression', 'parameters': {},
                         'features': FEATURE_COLUMNS, 'fingerprint': 'test-fixture'}
            approval = {'county_fips': ['06037', '12086', '48201'],
                        'training_years': [2018, 2019, 2020], 'validation_years': [2021],
                        'horizon_minutes': 180, 'required_future_quarter_hours': 12,
                        'minimum_absolute_increase': 200, 'minimum_relative_increase': .5,
                        'positive_current_count_required': True}
            metadata = freeze_pipeline(root, frame, selection, approval)
            proof = verify_development_reload(root)
            self.assertEqual(proof['maximum_score_error'], 0.)
            self.assertEqual(proof['rows'], 4)
            self.assertFalse((root / 'data/final_test').exists())
            (root / metadata['artifact']).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                freeze_pipeline(root, frame, selection, approval)

    def test_arrow_county_part_is_fingerprinted_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reports = root / 'reports'
            reports.mkdir()
            (reports / 'target_approval.json').write_text('{}', encoding='utf-8')
            data_path = 'data/windows/gold/county/label_audit'
            label_dir = root / data_path
            label_dir.mkdir(parents=True)
            part = label_dir / 'part-00000.parquet'
            part.write_bytes(b'original')
            sha = '0682c5f2076f099c34cfdd15a9e063849ed437a49677e6fcc5b4198c76575be5'
            (label_dir / '_gridrescue_storage.json').write_text(json.dumps({
                'format': 'gridrescue-arrow-local-v1', 'rows': 1,
                'parts': [{'name': part.name, 'sha256': sha}],
            }), encoding='utf-8')
            proof = {'status': 'VERIFIED', 'storage_backend': 'arrow-local', 'scopes': {'county': {
                'persisted_stage_counts': {'label_audit': 1},
                'full_content_roundtrips': {data_path: {'rows': 1, 'missing_or_changed_rows': 0,
                                                       'extra_or_changed_rows': 0}},
            }}}
            (reports / 'persistence_validation.json').write_text(json.dumps(proof), encoding='utf-8')
            _, inputs = fingerprint(root)
            self.assertEqual(inputs['data'], [(part.name, sha)])
            part.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                fingerprint(root)

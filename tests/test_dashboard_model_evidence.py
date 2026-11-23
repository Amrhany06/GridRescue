"""Dashboard must show only completed, reload-verified model evidence."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gridrescue.dashboard_data import load_model_result

class ModelEvidenceTests(unittest.TestCase):
    def test_no_result_is_not_a_validated_model(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(load_model_result(Path(directory)))

    def test_requires_completed_journal_and_matching_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            out=root/'reports/modeling'; out.mkdir(parents=True)
            result={'status':'VERIFIED_FINAL_EVALUATION','artifact_sha256':'fixture','final_evaluation_count':1,'metrics':{'rows':12}}
            path=out/'final_evaluation.json'; path.write_text(json.dumps(result),encoding='utf-8')
            (out/'final_evaluation_journal.json').write_text(json.dumps({'status':'COMPLETE','result_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
            (out/'reload_validation.json').write_text(json.dumps({'status':'VERIFIED','artifact_sha256':'different'}))
            with self.assertRaisesRegex(ValueError,'reload'):
                load_model_result(root)
            (out/'reload_validation.json').write_text(json.dumps({'status':'VERIFIED','artifact_sha256':'fixture'}))
            self.assertEqual(load_model_result(root),result)
            (out/'final_evaluation_journal.json').write_text(json.dumps({'status':'STARTED'}))
            with self.assertRaisesRegex(ValueError,'completed'):
                load_model_result(root)

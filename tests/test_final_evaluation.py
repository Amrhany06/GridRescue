"""Held-out replay must not permit repeat access or modified evidence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gridrescue.experiment import digest,write_json
from gridrescue.final_evaluation import completed_result


class FinalEvaluationTests(unittest.TestCase):
    def test_interrupted_evaluation_cannot_silently_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            write_json(root/'reports/modeling/final_evaluation_journal.json',{'status':'STARTED'})
            with self.assertRaisesRegex(RuntimeError,'recovery approval'):
                completed_result(root,{'frozen':True})

    def test_completed_replay_rejects_changed_prediction_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            selection={'frozen':True,'model':'fixture'}
            for name in ['artifact','predictions','reload_sample']:
                (root/name).write_bytes(b'original')
            result={'status':'VERIFIED_FINAL_EVALUATION','selection':selection}
            for name in ['artifact','predictions','reload_sample']:
                result[name]=name
                result[name+'_sha256']=digest(root/name)
            path=root/'reports/modeling/final_evaluation.json'
            write_json(path,result)
            write_json(root/'reports/modeling/final_evaluation_journal.json',{'status':'COMPLETE','result_sha256':digest(path)})
            self.assertEqual(completed_result(root,selection),result)
            (root/'predictions').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'hash mismatch'):
                completed_result(root,selection)

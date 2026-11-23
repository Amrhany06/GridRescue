"""Chronology, preprocessing and once-only final evaluation regression checks."""
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gridrescue.modeling import FEATURE_COLUMNS, chronological_folds, make_model, classification_metrics, claim_final_evaluation, validate_development


class ModelingTests(unittest.TestCase):
    def test_time_embargo_excludes_boundary_labels_and_2021(self):
        times=['2018-01-01 00:00','2018-01-01 00:15','2018-06-30 21:00',
               '2018-07-01 00:00','2018-07-01 00:15','2019-01-01 00:00','2019-01-01 00:15',
               '2020-01-01 00:00','2020-01-01 00:15','2021-01-01 00:00','2021-01-01 00:15']
        frame=pd.DataFrame({'timestamp':pd.to_datetime(times,utc=True),'candidate_y':[0,1,0,0,1,0,1,0,1,0,1]})
        folds=chronological_folds(frame)
        self.assertEqual(len(folds),3)
        self.assertEqual(folds[0]['train'].tolist(),[0,1])
        self.assertEqual(folds[0]['validation'].tolist(),[3,4])
        for fold in folds:
            train=frame.iloc[fold['train']]
            validation=frame.iloc[fold['validation']]
            self.assertLess(train.timestamp.max()+pd.Timedelta(hours=3),validation.timestamp.min())
            self.assertTrue((validation.timestamp.dt.year<=2020).all())

    def test_pipeline_learns_only_training_and_ignores_future_metadata(self):
        frame=pd.DataFrame({c:[1.,3.,5.,7.] for c in FEATURE_COLUMNS})
        pipeline=make_model('Logistic Regression')
        pipeline.fit(frame,np.array([0,0,1,1]))
        numeric=pipeline.named_steps['prepare'].named_transformers_['numeric']
        self.assertEqual(numeric.named_steps['imputer'].statistics_[0],4.)
        self.assertEqual(numeric.named_steps['scaler'].mean_[0],4.)
        validation=pd.DataFrame({c:[999.] for c in FEATURE_COLUMNS})
        before=pipeline.predict_proba(validation)
        validation['future_max']=1.e15
        np.testing.assert_allclose(before,pipeline.predict_proba(validation))
        self.assertEqual(numeric.named_steps['scaler'].mean_[0],4.)

    def test_metrics_handle_single_class_without_fabricated_roc_auc(self):
        result=classification_metrics(np.array([0,0]),np.array([0.1,0.2]))
        self.assertIsNone(result['roc_auc'])
        self.assertEqual(result['confusion_matrix'],[[2,0],[0,0]])
        self.assertEqual(result['accuracy'],1.)

    def test_half_probability_tie_uses_sklearn_negative_class(self):
        result=classification_metrics(np.array([0]),np.array([0.5]))
        self.assertEqual(result['confusion_matrix'],[[1,0],[0,0]])

    def test_final_evaluation_requires_frozen_choice_and_cannot_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'journal.json'
            with self.assertRaises(ValueError):
                claim_final_evaluation(path,{'frozen':False})
            self.assertFalse(path.exists())
            claim_final_evaluation(path,{'frozen':True,'model':'fixture'})
            with self.assertRaises(FileExistsError):
                claim_final_evaluation(path,{'frozen':True,'model':'fixture'})

    def test_development_guard_rejects_test_year(self):
        frame=pd.DataFrame({'timestamp':pd.to_datetime(['2022-01-01'],utc=True)})
        with self.assertRaisesRegex(ValueError,'2022'):
            validate_development(frame)

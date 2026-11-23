"""Reload only our hash-verified saved pipeline and reproduce sample outputs."""
import json
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.experiment import digest,write_json,probability
from gridrescue.modeling import FEATURE_COLUMNS

def main():
    result=json.loads((ROOT/'reports/modeling/final_evaluation.json').read_text(encoding='utf-8'))
    artifact=ROOT/result['artifact']
    sample_path=ROOT/result['reload_sample']
    assert digest(artifact)==result['artifact_sha256']
    assert digest(sample_path)==result['reload_sample_sha256']
    pipeline=joblib.load(artifact)
    sample=pd.read_parquet(sample_path)
    predicted=probability(pipeline,sample[FEATURE_COLUMNS])
    np.testing.assert_allclose(predicted,sample.expected_probability,rtol=0,atol=1e-12)
    np.testing.assert_array_equal(pipeline.predict(sample[FEATURE_COLUMNS]),sample.expected_prediction)
    report={'status':'VERIFIED','fresh_process':True,'pid':__import__('os').getpid(),
            'python':sys.executable,'rows':len(sample),'features':FEATURE_COLUMNS,
            'maximum_probability_error':float(np.abs(predicted-sample.expected_probability).max()),
            'artifact_sha256':digest(artifact),'preprocessing_and_estimator_reloaded':True,
            'raw_test_data_reopened':False,'refit':False}
    write_json(ROOT/'reports/modeling/reload_validation.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()

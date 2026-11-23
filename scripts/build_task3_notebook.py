"""Extend the previous gated Task 3 plan; preserve its original as a checkpoint."""
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
from build_notebooks import md,code

ROOT=Path(__file__).resolve().parents[1]

def cells():
    return [
        md('''# Task 3 — Classification research, validation and comparison
        University experiment: Logistic Regression, Decision Tree Classifier and Random Forest Classifier.
        The user replaced Histogram Gradient Boosting before any real-data training.
        We predict **reported escalation**, not outage occurrence, restoration, or national operational risk.
        The approved population is eligible observations in Los Angeles, Miami-Dade and Harris counties.
        The target, thirteen input features, chronological partitions and completeness rules are unchanged.
        Saved evidence may be replayed when its data/code/configuration hashes match; no saved score is an invented rerun.
        '''),
        code('''
        from pathlib import Path
        import sys,json
        ROOT=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'src/gridrescue/pipeline.py').exists())
        sys.path.insert(0,str(ROOT/'src'))
        import numpy as np,pandas as pd,matplotlib.pyplot as plt
        from IPython.display import display,Markdown
        from gridrescue.experiment import run_development,load_development,slug
        from gridrescue.modeling import FEATURE_COLUMNS,MODEL_NAMES,SEARCH,chronological_folds
        from gridrescue.final_evaluation import run_final,verify_reload
        display(json.loads((ROOT/'reports/target_approval.json').read_text()))
        persistence=json.loads((ROOT/'reports/persistence_validation.json').read_text())
        assert persistence['status']=='VERIFIED'
        display(persistence)
        '''),
        md('''## 01 Research and algorithm selection
        This is supervised binary classification. Average precision (AP) is the primary ranking criterion;
        it summarizes precision across recall thresholds and is useful when class prevalence differs.
        AP and trapezoidal area under the precision–recall curve are reported separately. Accuracy alone
        can conceal missed positives. The classification threshold stays at 0.5; exact ties use class 0.

        | Model | How it works and why chosen | Strengths and limitations | Parameters investigated |
        |---|---|---|---|
        | Logistic Regression | Learns a linear score in log-odds, then converts it to a probability | Simple interpretable reference; scaling matters; linear boundary can underfit nonlinear escalation | C, inverse regularization strength |
        | Decision Tree Classifier | Repeatedly splits a feature to reduce class impurity | Captures nonlinear thresholds/interactions; one deep tree can memorize and change greatly with data | max_depth; min_samples_split; min_samples_leaf |
        | Random Forest Classifier | Averages randomized trees trained on bootstrap samples and feature subsets | Reduces a single tree's variance; captures interactions; more compute and less direct interpretation | n_estimators; max_depth; min_samples_leaf |

        Research references: [Logistic Regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression),
        [Decision trees](https://scikit-learn.org/stable/modules/tree.html),
        [Random forests](https://scikit-learn.org/stable/modules/ensemble.html#forest).
        Full research notes, default parameter definitions and tradeoffs: `docs/MODEL_RESEARCH.md`.
        '''),
        code('''
        development=load_development(ROOT)
        display(development.groupby(['split','candidate_y']).size().unstack(fill_value=0))
        display(development.groupby('split').timestamp.agg(['min','max']))
        display(pd.DataFrame({'feature':FEATURE_COLUMNS,'type':'numeric'}))
        print('All identifiers, future counts/slots, threshold and target are excluded from X.')
        print('Target: current>0; future max >= current + max(200,0.5*current); all twelve future quarter-hours required.')
        assert len(development)==406240
        '''),
        md('''## 02 Pipelines and default baselines
        Each pipeline selects the same numeric allowlist, imputes missing predictors with training medians,
        standardizes using training means/population standard deviations, and fits a classifier.
        Geography and timestamp are audit metadata, so no categorical encoding is necessary.
        Trees do not require scaling, but keeping this monotonic transform makes preparation consistent.
        Task 2 Spark artifacts remain separate: their sample standard deviation and approximate median
        are not substituted for scikit-learn fold fitting.

        **Execution order:** all three default full-training baselines first; common default CV second;
        bounded tuning third. Only random_state=17 and RF n_jobs=2 change essential execution settings.
        Actual convergence warnings are retained. If LR needs more iterations, max_iter=1000 is used
        only in documented tuned candidates; the recorded default remains the genuine default.
        This cell executes the experiment or replays matching hash-verified evidence. No 2022 data is read.
        '''),
        code('''
        dev=run_development(ROOT)
        baseline_rows=[]
        for result in dev['default_baselines']:
            baseline_rows.append({'model':result['model'],'fit_seconds':result['fit_seconds'],
                                  'warnings':result['warnings'],**result['validation']})
            display({'model':result['model'],'actual_default_settings':result['classifier_parameters']})
        display(pd.DataFrame(baseline_rows))
        '''),
        md('''## 03 Time-aware validation and generalization
        The three expanding folds train before July 2018 / January 2019 / January 2020 and validate
        on the following half-year / year / year. Training label endpoints must be strictly before
        validation starts; evaluation endpoints must stay inside their interval. All counties share
        these time boundaries. A gap of at least three hours prevents shared future label observations
        across the boundary. Past-only history at a validation anchor is available at prediction time.
        2021 stays outside CV and tuning, then selects the winning algorithm; 2022 remains sealed.
        Preprocessing is fitted anew within every fold. Folds use identical cohorts for all models.
        '''),
        code('''
        cv_rows=[]
        fold_rows=[]
        for result in dev['default_cv']:
            row={'model':result['model']}
            for metric,value in result['summary'].items():
                row[metric]=f"{value['mean']:.4f} ± {value['std']:.4f}"
            cv_rows.append(row)
            for fold in result['folds']:
                fold_rows.append({'model':result['model'],'fold':fold['name'],'train_rows':fold['train_rows'],
                  'validation_rows':fold['validation_rows'],'embargo_hours':fold['embargo_seconds']/3600,
                  'train_AP':fold['train']['average_precision'],'validation_AP':fold['validation']['average_precision'],
                  'fit_seconds':fold['fit_seconds']})
        display(pd.DataFrame(cv_rows))
        display(pd.DataFrame(fold_rows))
        assert all(row['embargo_hours']>=3 for row in fold_rows)
        print('Fold SD describes temporal variation, not an independent-event confidence interval.')
        '''),
        md('''## 04 Bounded tuning
        A documented manual search uses only the same training-period folds. The default is retained
        as a candidate. DT contrasts depth 12 vs 20, split minimum 2 vs 20, leaf minimum 1 vs 10.
        RF contrasts 100 vs 200 trees, depth 12 vs 20, leaf minimum 5 vs 10. These controlled contrasts
        investigate every requested parameter with bounded cost; they do not establish a global optimum.
        Larger leaves and restricted depth can reduce overfitting. More trees can stabilize an ensemble
        but increase runtime. LR compares C=0.1 and 10 against default C=1.
        '''),
        code('''
        tuning=[]
        for search in dev['searches']:
            for result in search['candidates']:
                tuning.append({'model':search['model'],'parameters':result['parameters'],
                    'CV_AP_mean':result['summary']['average_precision']['mean'],
                    'CV_AP_SD':result['summary']['average_precision']['std'],
                    'CV_fit_seconds':result['total_fit_seconds'],
                    'selected':result['parameters']==search['selected_parameters']})
        display(pd.DataFrame(tuning))
        '''),
        md('''## 05 Comparison, metrics and model choice
        Compare defaults and CV-selected configurations on the same 2021 population, including training
        time and train/validation performance. All required classification metrics appear below.
        The winner is frozen using highest 2021 AP among the three CV-selected configurations.
        It is possible that a default beats the bounded alternatives; in that case keep the default.
        '''),
        code('''
        display(pd.DataFrame(dev['comparison']))
        selected=dev['selected']
        for choice in selected:
            result=choice['full_fit']
            gap=result['train']['average_precision']-result['validation']['average_precision']
            display(Markdown(f"**{choice['model']}:** train AP {result['train']['average_precision']:.4f}; 2021 AP {result['validation']['average_precision']:.4f}; gap {gap:.4f}. A large positive gap suggests overfitting or temporal distribution change; it does not isolate their causes."))
        display(dev['frozen_selection'])
        display(Markdown(f"**Selected:** {dev['frozen_selection']['model']}, based on development AP {dev['frozen_selection']['validation_average_precision']:.4f}. No 2022 metric enters this choice."))
        '''),
        code('''
        from sklearn.metrics import roc_curve,precision_recall_curve,ConfusionMatrixDisplay
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        for choice in selected:
            prediction=pd.read_parquet(ROOT/choice['full_fit']['predictions'])
            fpr,tpr,_=roc_curve(prediction.candidate_y,prediction.probability)
            precision,recall,_=precision_recall_curve(prediction.candidate_y,prediction.probability)
            axes[0].plot(fpr,tpr,label=choice['model'])
            axes[1].plot(recall,precision,label=choice['model'])
        axes[0].plot([0,1],[0,1],'k--',alpha=.4)
        axes[0].set(xlabel='False-positive rate',ylabel='True-positive rate',title='2021 ROC curves')
        axes[1].set(xlabel='Recall',ylabel='Precision',title='2021 precision–recall curves')
        for ax in axes: ax.legend()
        plt.tight_layout(); plt.show()
        fig,axes=plt.subplots(2,3,figsize=(13,8))
        for column,(baseline,choice) in enumerate(zip(dev['default_baselines'],selected)):
            for row,(name,result) in enumerate([('default',baseline),('CV selected',choice['full_fit'])]):
                ConfusionMatrixDisplay(np.array(result['validation']['confusion_matrix']),display_labels=[0,1]).plot(ax=axes[row,column],colorbar=False)
                axes[row,column].set_title(f"{result['model']} — {name}")
        plt.tight_layout(); plt.show()
        '''),
        md('''Class imbalance is measured, not assumed: the prefix and three-county cohorts have different
        class distributions, and 2021/2022 may differ. A negative prediction means no threshold crossing
        in a fully observed three-hour window; it does not mean electricity was restored. False negatives
        miss escalations, while false positives predict a rise that was not observed. No cost-optimal or
        calibrated operational alert threshold has been established.
        '''),
        md('''## 06 Final refit and one held-out evaluation
        This guarded cell checks the frozen choice, refits its complete pipeline on eligible 2018–2021
        development observations, then records an exclusive access journal BEFORE opening 2022.
        Only the same three counties are extracted. The unchanged completeness, quality, feature and
        boundary rules apply. Results are stored permanently; clean-kernel reruns replay this evidence.
        An interrupted evaluation refuses a silent repeat and requires explicit recovery approval.
        '''),
        code('''
        final=run_final(ROOT)
        display({'selected_model':final['selection']['model'],'final_development_rows':final['development_rows'],
                 'fit_seconds':final['final_refit_seconds'],'evaluation_count':final['final_evaluation_count']})
        display(final['extraction']); display(final['cleaning']); display(pd.DataFrame(final['coverage']))
        display(final['metrics']); display(pd.DataFrame(final['county_metrics']).T)
        display({'excluded_clean_anchors':final['label_exclusions'],'label_counts':final['label_counts']})
        '''),
        code('''
        prediction=pd.read_parquet(ROOT/final['predictions'])
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        ConfusionMatrixDisplay(np.array(final['metrics']['confusion_matrix']),display_labels=[0,1]).plot(ax=axes[0],colorbar=False)
        fpr,tpr,_=roc_curve(prediction.candidate_y,prediction.probability)
        precision,recall,_=precision_recall_curve(prediction.candidate_y,prediction.probability)
        axes[1].plot(fpr,tpr); axes[1].set(xlabel='False-positive rate',ylabel='True-positive rate',title='Final 2022 ROC')
        axes[2].plot(recall,precision); axes[2].set(xlabel='Recall',ylabel='Precision',title='Final 2022 precision–recall')
        plt.tight_layout(); plt.show()
        display(Markdown(f"Final AP {final['metrics']['average_precision']:.4f}, ROC-AUC {final['metrics']['roc_auc']:.4f}, F1 {final['metrics']['f1']:.4f}, with prevalence {final['metrics']['prevalence']:.2%}. These are dependent county-time anchors, not independent outage events. This held-out result cannot be used to revise the model and retest."))
        '''),
        md('''## 07 Save, reload and inference contract
        `artifacts/modeling/selected_pipeline.joblib` contains the feature selector, median imputer,
        scaler and estimator together. The final report records feature order, parameters, versions,
        source/code hashes and metrics. Only load trusted joblib files: deserialization executes code.
        A separate fresh Python process checks the artifact hash and reproduces 100 saved sample
        probabilities/classes without refitting or reopening raw test data. Input consists of the thirteen
        engineered current/past features, requiring up to one hour of observed county history.
        '''),
        code('''
        reload_evidence=verify_reload(ROOT)
        display(reload_evidence)
        assert reload_evidence['status']=='VERIFIED' and reload_evidence['fresh_process']
        print('Inference: pipeline.predict_proba(engineered_frame[FEATURE_COLUMNS])[:,1]')
        print('Class: pipeline.predict(engineered_frame[FEATURE_COLUMNS]); unchanged threshold 0.5.')
        display(Markdown('**Limits:** ' + '; '.join(final['limitations']) + '.'))
        print('Complete cases select persistent reported outages. 99.80% of development anchors overlap a preceding eligible three-hour window.')
        print('A three-county model is not nationally representative. No live monitoring or operational validity is claimed.')
        print('Evidence: reports/modeling/{development,final_evaluation,reload_validation}.json; comparison.csv; frozen_selection.json.')
        '''),
    ]

def main():
    path=ROOT/'notebooks/task3_modeling.ipynb'
    current=cells()
    for index,cell in enumerate(current): cell['id']=f'task3_modeling-{index:03d}'
    notebook={'cells':current,'metadata':{'kernelspec':{'name':'python3','display_name':'GridRescue Linux','language':'python'},
               'language_info':{'name':'python','version':'3.12'}},'nbformat':4,'nbformat_minor':5}
    if path.exists():
        backup=ROOT/'artifacts/notebook_source_backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')/path.name
        backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,backup)
        old=json.loads(path.read_text(encoding='utf-8'))
        old_by_id={cell.get('id'):cell for cell in old['cells']}
        for cell in current:
            previous=old_by_id.get(cell['id'])
            if previous and previous['source']==cell['source']: cell.update(previous)
    path.write_text(json.dumps(notebook,indent=1,ensure_ascii=False),encoding='utf-8')
    print(f'Task 3: {sum(c["cell_type"]=="code" for c in current)} code cells; execution remains separate.')

if __name__=='__main__': main()

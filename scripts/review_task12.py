"""Inspect executed Task 1/2 evidence and write the user review package.

No raw CSV access, fitting, CV, tuning or held-out evaluation occurs here.
"""
import ast
import base64
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime,timezone
from pathlib import Path

import nbformat
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def read(name): return json.loads((ROOT/name).read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,text): (ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')

TASK1=[
('Read Data / original columns','task1_eda-003','pipeline.read_source','Five-column schema; bounded raw table','Why keep FIPS and invalid tokens as strings?'),
('Random Sample Data','task1_eda-005','Spark rand/orderBy','Ten actual prefix rows','Why is this not a random national sample?'),
('Size / scope / source coverage','task1_eda-scope-ledger','Previously executed full_source_audit; inventory','Full-development integrity table and three-scope ledger','What exactly explains the five-row discrepancy?'),
('Types, non-null counts and memory','task1_eda-009','Spark aggregation; psutil','Schema and distinct memory measurements','Why are file bytes, Python RSS and JVM cache different?'),
('Names / description / unique values','task1_eda-015','Spark describe/countDistinct','Original column meanings; summary statistics','Why is a county code not a magnitude predictor?'),
('Class balance','task1_eda-017','pipeline.audit_labels','Complete, incomplete, positive and negative counts','Why can an incomplete window not become class 0?'),
('Missing / invalid / cleaning impact','task1_eda-quarantine','pipeline.clean; storage.read_frame','Actual rejected rows, reasons and disjoint removal ledger','Which rows were removed at each stage? Why not zero-fill?'),
('Exact duplicates versus key conflicts','task1_eda-021','pipeline.clean','Reconciliation, uniqueness assertion and actual implementation','Why quarantine all conflicting variants instead of taking the first?'),
('Outlier Detection / Treatment','task1_eda-025','Spark approxQuantile; display-only log1p','IQR fence, real extremes, box/histogram and treatment comparison','Does exceeding the IQR fence prove an error?'),
('Univariate Analysis','task1_eda-027','Spark aggregation; bounded plotting','Outage-size distribution and UTC-hour coverage','Does a row count equal affected people or outage events?'),
('Feature versus Target','task1_eda-029','Spark grouped means','Measured class-conditional severity and past change','How does the target definition affect these associations?'),
('Feature-to-Feature / Correlation','task1_eda-033','pipeline.features; bounded correlation','Scatterplots and pairwise-complete Pearson matrix','What do skew and missing pairs do to interpretation?'),
('GroupBy / Statistical Summaries','task1_eda-035','Spark groupBy/agg','State observation coverage and severity summaries','Are these comparisons nationally representative?'),
('Full-year county context','task1_eda-county-context','dashboard_data.load_scope; verified Spark daily exports','Monthly county severity beside observation coverage','Why compare coverage alongside severity?'),
('Final findings / decisions','task1_eda-037','Measured audit reports','Concise counts, policies and scope limitations','Which findings are national integrity facts and which are subset EDA?'),
]
TASK2=[
('Identify Features','task2_preprocessing-feature-dictionary','pipeline.PREDICTORS / features','Exact ordered thirteen-feature dictionary','What is available at prediction time? Which columns are excluded?'),
('Create / Review Features','task2_preprocessing-005','pipeline.features','Actual feature rows and shared implementation source','What are transformations, actions, joins and windows doing?'),
('Exact lag / rolling / missing indicators','task2_preprocessing-manual-window','pipeline.features; independent bounded arithmetic','Five real history rows, exact lags, mean/variance and missing-lag rows','Why are four previous reports not necessarily one hour?'),
('Define X and approved y','task2_preprocessing-009','pipeline.audit_labels','Input allowlist and class/completeness table','State the exact threshold and twelve-slot completeness rule.'),
('Positive / negative / incomplete examples','task2_preprocessing-011','pipeline.audit_labels; expected-time comparison','Actual trajectories and missing expected quarter-hours','Why does even a partially observed positive remain excluded?'),
('Eligibility and selection impact','task2_preprocessing-eligibility-stages','Spark conditional aggregation','Nested counts for both scopes and exclusions','Why must nested stage counts not be summed as removals?'),
('Chronological Split / Avoid Leakage','task2_preprocessing-014','pipeline.split_tag / audit_labels','Train/validation counts and boundary assertions','How do past-only X, purged horizons and fold-only fitting prevent leakage?'),
('Missing Values / Categorical Encoding','task2_preprocessing-017','pipeline.fit_preparation','Loaded genuine Spark stages; numeric-only decision','Does predictor imputation invent missing observations or labels?'),
('Scaling and fitted training statistics','task2_preprocessing-scaling-example','Spark ImputerModel / StandardScalerModel','Thirteen fitted medians/means/sample stds and real before/after values','Why fit only training? What happens to a zero-variance predictor?'),
('Three-county Task 2 summary','task2_preprocessing-county-summary','Verified county audit, fitted JSON and persistence report','Separate train/validation counts, prevalence, eligible predictor nulls and all thirteen training statistics','Why do these statistics differ from the January-prefix examples?'),
('Check Outputs / Validate Features','task2_preprocessing-021','PipelineModel.transform; vector_to_array','Bounded rows/vectors; dimensions, class/split sizes and finite checks','What does each position in the final vector represent?'),
('Save Preparation / Reload','task2_preprocessing-023','storage.write_frame / read_frame / save_preparation / load_preparation','Two-scope fresh-process parity summary and artifact paths','Why is Arrow-local a workaround rather than a native Hadoop repair?'),
]

def main():
    now=datetime.now(timezone.utc).isoformat()
    persistence=read('reports/persistence_validation.json')
    assert persistence['status']=='VERIFIED' and persistence['storage_backend']=='arrow-local'
    assert persistence['fresh_process'] and not persistence['2022_accessed']
    for result in persistence['scopes'].values():
        assert result['original_fitted_statistics_equal'] and len(result['feature_order'])==13
        assert result['rows_exercising_missing_history']>0
        assert result['exact_vector_mismatches']==result['nonfinite_vectors']==result['dimension_errors']==0
        assert len(result['full_content_roundtrips'])==7
        assert all(check['schema_equal_including_nullability_and_metadata'] and check['missing_or_changed_rows']==check['extra_or_changed_rows']==0 for check in result['full_content_roundtrips'].values())
    execution=read('reports/windows_notebook_execution.json')
    assert execution['clean_kernel_per_notebook'] and execution['mode']=='arrow-local'
    assert {item['name'] for item in execution['notebooks']}=={'task1_eda','task2_preprocessing'}
    assert all(item['status']=='VERIFIED' for item in execution['notebooks'])
    final_task1=ROOT/'reports/windows_task1_final_execution.json'
    if final_task1.exists():
        last=read('reports/windows_task1_final_execution.json')
        assert last['mode']=='arrow-local' and last['clean_kernel_per_notebook']
        assert len(last['notebooks'])==1 and last['notebooks'][0]['name']=='task1_eda' and last['notebooks'][0]['status']=='VERIFIED'
        execution['notebooks']=[last['notebooks'][0],next(item for item in execution['notebooks'] if item['name']=='task2_preprocessing')]
        execution['source_execution_reports']=['reports/windows_task1_final_execution.json','reports/windows_notebook_execution.json']
        execution['composition_note']='Latest actual clean-kernel run for each notebook; separate kernels and invocation times are preserved.'
    final_task2=ROOT/'reports/windows_task2_final_execution.json'
    if final_task2.exists():
        last=read('reports/windows_task2_final_execution.json')
        assert last['mode']=='arrow-local' and last['clean_kernel_per_notebook']
        assert len(last['notebooks'])==1 and last['notebooks'][0]['name']=='task2_preprocessing' and last['notebooks'][0]['status']=='VERIFIED'
        execution['notebooks']=[next(item for item in execution['notebooks'] if item['name']=='task1_eda'),last['notebooks'][0]]
        execution['source_execution_reports']=['reports/windows_task1_final_execution.json','reports/windows_task2_final_execution.json']
    focused_path=ROOT/'reports/task12_focused_execution.json'
    if focused_path.exists():
        focused=read('reports/task12_focused_execution.json')
        assert focused['mode']=='arrow-local' and focused['clean_kernel_per_notebook']
        assert {item['name'] for item in focused['notebooks']}=={'task1_eda','task2_preprocessing'}
        assert all(item['status']=='VERIFIED' for item in focused['notebooks'])
        execution=focused
        execution['source_execution_reports']=['reports/task12_focused_execution.json']
    write('reports/task12_clean_kernel_execution.json',json.dumps(execution,indent=2))
    notebook_checks=[]
    plot_dir=ROOT/'artifacts/notebook_review/windows'; plot_dir.mkdir(parents=True,exist_ok=True)
    for name,minimum_plots in [('task1_eda',9),('task2_preprocessing',0)]:
        notebook=nbformat.read(ROOT/'notebooks'/f'{name}.ipynb',as_version=4); nbformat.validate(notebook)
        cells=[cell for cell in notebook.cells if cell.cell_type=='code']
        assert [cell.execution_count for cell in cells]==list(range(1,len(cells)+1))
        images=[]; largest_text=0
        for cell in cells:
            for output in cell.outputs:
                assert output.output_type!='error'
                largest_text=max(largest_text,len(output.get('text','')),len(output.get('data',{}).get('text/plain','')))
                png=output.get('data',{}).get('image/png')
                if png:
                    raw=base64.b64decode(png)
                    with Image.open(io.BytesIO(raw)) as im: im.load(); dimensions=im.size
                    path=plot_dir/f'{name}_{len(images)+1:02d}.png'; path.write_bytes(raw)
                    images.append({'path':path.relative_to(ROOT).as_posix(),'dimensions':dimensions})
        assert len(images)>=minimum_plots
        assert largest_text<40000,'Review outputs are unexpectedly large'
        notebook_checks.append({'notebook':name,'total_cells':len(notebook.cells),'executed_code_cells':len(cells),
            'saved_errors':0,'saved_png_plots':len(images),'plots':images,'largest_plain_text_output_characters':largest_text,
            'sha256':digest(ROOT/'notebooks'/f'{name}.ipynb')})
    pause=read('reports/training_pause.json')
    assert all(digest(ROOT/path)==expected for path,expected in pause['frozen_code_sha256'].items())
    assert not (ROOT/'reports/modeling/development.json').exists() and not (ROOT/'reports/modeling/final_evaluation_journal.json').exists()
    assert not (ROOT/'artifacts/modeling').exists() and not (ROOT/'data/final_test').exists()
    task3=nbformat.read(ROOT/'notebooks/task3_modeling.ipynb',as_version=4)
    assert all(cell.get('execution_count') is None for cell in task3.cells if cell.cell_type=='code')
    # Confirm the original native integration test was not relaxed or rerouted.
    checkpoint=read('reports/windows_recovery_checkpoint.json')
    with zipfile.ZipFile(ROOT/checkpoint['archive']) as archive:
        original=archive.read('tests/test_pipeline.py').decode('utf-8-sig')
    assert ast.dump(ast.parse(original))==ast.dump(ast.parse((ROOT/'tests/test_pipeline.py').read_text()))
    tests=(ROOT/'reports/verification/tests.txt').read_text(encoding='utf-8')
    total=int(re.findall(r'Ran (\d+) tests',tests)[-1])
    errors=re.findall(r'^ERROR: (test_\w+)',tests,re.MULTILINE)
    assert errors==['test_preparation_fits_only_training_and_saves_reload']
    assert 'FAILED (errors=1)' in tests
    markdown_render=read('reports/notebook_markdown_rendering.json') if (ROOT/'reports/notebook_markdown_rendering.json').exists() else {}
    markdown_check=read('reports/verification/notebook_markdown.json') if (ROOT/'reports/verification/notebook_markdown.json').exists() else {}
    if focused_path.exists():
        assert markdown_render.get('status')=='VERIFIED_GFM_MARKDOWN_RENDERING'
        assert markdown_check.get('exit_code')==0
        assert all(n['after']['unintended_code_blocks']==0 and n['after']['rendered_headings']==n['after']['expected_headings'] for n in markdown_render['notebooks'])
    result={'status':'READY_FOR_USER_REVIEW_ARROW_LOCAL','utc':now,'notebooks':notebook_checks,
        'persistence':'VERIFIED_ARROW_LOCAL_ONLY','native_hadoop_writer':'BLOCKED; original native integration test retained unchanged',
        'tests':{'total':total,'passed':total-1,'errors':1,'native_blocker':errors[0],
                 'scope':'Prior full-suite evidence; unchanged native blocker. Not rerun for this notebook-only revision because classifier fitting is prohibited.'},
        'training_configuration_hashes_unchanged':True,'real_data_task3_training_executed':False,'2022_evaluation_executed':False,
        'focused_notebook_checks':{'markdown_regressions':markdown_check,'markdown_rendering':markdown_render},
        'original_native_test_ast_unchanged':True,'user_review_required_before_task3':True}
    write('reports/task12_review_validation.json',json.dumps(result,indent=2))
    guide=['# Task 1 and Task 2 — notebook review guide','',
        'Open the executed notebooks in Jupyter or VS Code and follow the navigation table at the top. All changed/new code has been executed from a clean kernel. Every count below refers to its displayed scope. Task 3 remains PAUSED until the user approves these notebooks.','',
        'Spark performs parsing, cleaning, joins, windows, aggregation and fitted preparation. pandas is used only for bounded examples and compact plotting/export tables. Arrow-local performs local storage encoding; it does not replace Spark processing.','']
    for name,items in [('Task 1',TASK1),('Task 2',TASK2)]:
        guide+=['## '+name,'','| Section / cell ID | Responsible implementation | Key displayed evidence | Defense question |','|---|---|---|---|']
        guide+=['| '+section+' / `'+cid+'` | `'+function+'` | '+output+' | '+question+' |' for section,cid,function,output,question in items]
        guide+=['']
    guide+=['## Scope and storage contract','',
        'Full-source auditing establishes inventory and development integrity only. Prefix EDA uses the first 100,000 rows of each development year; the selected-county cohort uses all available 2018–2021 dates for three fixed counties. Neither is nationally representative. The 2022 inventory count is historical integrity metadata, not held-out feature/label access.','',
        'Read `WINDOWS_SPARK_DIAGNOSIS.md` and `persistence_validation.json` for exact schema/null/value/statistic parity, memory bounds, version coupling and the remaining native blocker. Previous executed Windows notebooks remain in `artifacts/windows_notebooks/`; the pre-recovery checkpoint is recorded in `windows_recovery_checkpoint.json`.','',
        'Reproduce without classifiers: `python scripts/run_pipeline.py --scope sample --storage arrow-local`, then `--scope county`, `python scripts/verify_persistence.py --storage arrow-local`, and `python scripts/execute_notebooks.py --mode arrow-local --notebook task1_eda --notebook task2_preprocessing --report reports/windows_notebook_execution.json`. Use the existing `.venv/Scripts/python.exe` for these commands.','',
        'Do not execute the Task 3 notebook or training/final-evaluation scripts during this review. No WSL distribution or environment was removed.']
    write('reports/NOTEBOOK_REVIEW_GUIDE.md','\n'.join(guide))
    rubric=['# Official Task 1/2 rubric — executed evidence','',
        'Source: the original three-page Task 1/2 PDFs in docs/requirements. PASS is scoped to the displayed real-data populations and verified Arrow-local persistence; it does not assert native Hadoop repair, national Gold processing, or completion of Task 3.','',
        '| Task | Original requirement | Status | Notebook evidence |','|---|---|---|---|']
    from update_acceptance import TASK1 as required1,TASK2 as required2
    for name,items in [('task1_eda',required1),('task2_preprocessing',required2)]:
        notebook=nbformat.read(ROOT/'notebooks'/f'{name}.ipynb',as_version=4)
        by_id={cell.id:cell for cell in notebook.cells}
        for requirement,index in items:
            cid=f'{name}-{index:03d}'; cell=by_id[cid]
            assert cell.get('execution_count') is not None and cell.get('outputs')
            rubric.append(f'| {name} | {requirement} | PASS | `{cid}`; executed cell {cell.execution_count} |')
    rubric+=['','Task 1 submission checklist: required sections/subsections, executable outputs/plots, observations, cleaning/treatment reasons, and concise findings are present. Task 2 stops before model selection/training. Complete Spark preprocessing is fitted/reloaded; native Hadoop writing remains a separately reported failed integration.','',
        'Additional required evidence: scope ledger, invalid-row examples and cleaning impact; manual full-year county lag/window example; thirteen-feature definitions; nested eligibility stages; real imputation/scaling example; saved 13-position vectors; fresh-process reload parity. See NOTEBOOK_REVIEW_GUIDE.md for exact IDs.']
    write('reports/TASK1_TASK2_RUBRIC_REVIEW.md','\n'.join(rubric))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()

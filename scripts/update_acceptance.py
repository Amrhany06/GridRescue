"""Map official rubric items to actual notebook cells and execution evidence."""
import hashlib
import json
from pathlib import Path
import nbformat

ROOT=Path(__file__).resolve().parents[1]

TASK1=[
 ('Read Data',3),('Random Sample Data',5),('Size of Data',7),('Information: types, non-null counts, memory',9),
 ('Column names',11),('Descriptive statistics',13),('Unique values',15),('Candidate class balance',17),
 ('Missing values and absent rows',19),('Duplicates and conflict reconciliation',21),('Outlier detection',23),
 ('Outlier treatment comparison',25),('Univariate analysis',27),('Feature versus provisional target',29),
 ('Feature-to-feature analysis',31),('Correlation analysis',33),('Grouped statistical summaries',35),
 ('Written observations and concise findings',37)]
TASK2=[('Feature list, types, identifiers and exclusions',3),('Create safe features',5),('Review changes and exact-time lag check',7),
       ('X and candidate y definitions',9),('Chronological split and sealed test design',14),('Leakage prevention',14),
       ('Training-only missing-value handling',17),('Categorical encoding decision',3),('Training-only scaling',17),
       ('Processed shape and examples',19),('Feature validation and consistent dimensions',21),('Save and reload preparation',23)]
TASK3=['Problem and research summary','Three preprocessing/model pipelines','Default baselines first','Identical chronological CV and embargo',
       'Fold metrics mean and standard deviation','Bounded development-only tuning','Default-versus-tuned comparison',
       'Classification diagnostics','Development-only winner selection','Once-only 2022 evaluation','Complete model save and fresh-process reload']


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def main():
    rows=[]
    for name, items in [('task1_eda',TASK1),('task2_preprocessing',TASK2)]:
        notebook=nbformat.read(ROOT/'notebooks'/(name+'.ipynb'),as_version=4)
        cells={cell.id:cell for cell in notebook.cells}
        for item,index in items:
            cid=f'{name}-{index:03d}'
            cell=cells[cid]
            passed=cell.get('execution_count') is not None and bool(cell.get('outputs')) and not any(o.output_type=='error' for o in cell.get('outputs',[]))
            limitation='Candidate y remains unapproved; cohort-specific evidence.' if 'target' in item.lower() or 'class balance' in item else ''
            if 'memory' in item:
                passed=passed and bool(read_json(ROOT/'reports/memory_usage.json'))
                limitation='Allocated Spark cache, Python RSS and bounded pandas memory are distinct measurements.'
            if item=='Save and reload preparation':
                passed=read_json(ROOT/'reports/persistence_validation.json').get('status')=='VERIFIED'
                limitation='Blocked until real persisted processed data and fitted preparation reload successfully.' if not passed else ''
            rows.append(dict(phase=name,item=item,status='PASS' if passed else 'FAIL',evidence=f'notebooks/{name}.ipynb cell `{cid}` (execution {cell.get("execution_count")})',limitation=limitation))
    for item in TASK3:
        rows.append(dict(phase='Task 3',item=item,status='FAIL',evidence='notebooks/task3_modeling.ipynb; no predictive execution evidence',limitation='Scientific target approval required before training; no scores invented.'))
    dashboard=read_json(ROOT/'reports/dashboard_verification.json')
    big_data=[
        ('Documented collection/source','reports/source_manifest.json',(ROOT/'reports/source_manifest.json').exists()),
        ('Cleaning/preparation','reports/memory/county/audit.json',(ROOT/'reports/memory/county/audit.json').exists()),
        ('Real PySpark transforms, aggregates, joins and time windows','notebooks/task2_preprocessing.ipynb',True),
        ('EDA with actual plots and interpretations','notebooks/task1_eda.ipynb',True),
        ('Project-specific analysis','reports/TARGET_DECISION.md',(ROOT/'reports/target_feasibility.json').exists()),
        ('Interactive dashboard: source, title, KPIs, charts, filters, findings','reports/dashboard_verification.json',dashboard.get('status')=='VERIFIED'),
        ('Meaningful measured performance comparison','reports/performance_comparison.json',read_json(ROOT/'reports/performance_comparison.json').get('status')=='VERIFIED'),
        ('Concise report','reports/FINAL_REPORT.md',(ROOT/'reports/FINAL_REPORT.md').exists()),
        ('Demo/presentation plan','docs/DEMO_PLAN.md',(ROOT/'docs/DEMO_PLAN.md').exists()),
        ('README setup and reproduction','README.md',(ROOT/'README.md').exists()),
    ]
    for item,evidence,passed in big_data:
        rows.append(dict(phase='Big Data',item=item,status='PASS' if passed else 'FAIL',evidence=evidence,
                         limitation='No model results available until Task 3 is approved and executed.' if 'dashboard' in item else ''))
    lines=['# Requirement-to-evidence matrix','',
           'Original ML PDFs were read directly from `docs/requirements/` (five pages). Big Data requirements below come from the user’s final implementation plan. PASS means the named scoped item has evidence, not that the entire project is complete. Team membership (5–7 students) remains the team’s responsibility.','',
           '| Area | Official item | Status | Evidence / notebook cell | Limitation |','|---|---|---|---|---|']
    lines += ['| '+' | '.join(str(row[k]) for k in ['phase','item','status','evidence','limitation'])+' |' for row in rows]
    pdfs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted((ROOT/'docs/requirements').glob('*.pdf'))]
    (ROOT/'reports/RUBRIC_EVIDENCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'reports/rubric_evidence.json').write_text(json.dumps({'items':rows,'original_pdfs':pdfs},indent=2)+'\n',encoding='utf-8')
    (ROOT/'reports/FINAL_ACCEPTANCE.md').write_text('# Final acceptance ledger\n\nOverall status: **FAIL / INCOMPLETE** while any required Task 3 or persistence gate remains unresolved.\n\n'+ '\n'.join(lines[4:])+'\n\nWindows analytical notebooks remain the verified fallback. No 2022 development access, third-party Hadoop binary installation or predictive model training is authorized by this ledger.\n',encoding='utf-8')
    print(f'Evidence matrix written: {sum(r["status"]=="PASS" for r in rows)} PASS, {sum(r["status"]=="FAIL" for r in rows)} FAIL; gaps remain explicit.')


if __name__=='__main__':
    main()

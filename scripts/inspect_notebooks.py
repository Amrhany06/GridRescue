"""Check saved cell execution and extract original plot PNGs for visual review."""
import base64
import json
from pathlib import Path
import nbformat

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'artifacts/notebook_review'
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for name in ['task1_eda', 'task2_preprocessing']:
        notebook = nbformat.read(ROOT / 'notebooks' / (name + '.ipynb'), as_version=4)
        nbformat.validate(notebook)
        code = [cell for cell in notebook.cells if cell.cell_type == 'code']
        assert [cell.execution_count for cell in code] == list(range(1, len(code)+1))
        plots = 0
        for cell in code:
            for output in cell.outputs:
                assert output.output_type != 'error'
                if 'image/png' in output.get('data', {}):
                    plots += 1
                    (out / f'{name}_{plots:02d}.png').write_bytes(base64.b64decode(output.data['image/png']))
        report.append(dict(notebook=name, executed_code_cells=len(code), saved_png_plots=plots,
                           output_blocks=sum(len(cell.outputs) for cell in code), saved_errors=0))
    (ROOT / 'reports/notebook_output_review.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

"""Regression checks for Jupyter prose, headings and existing navigation."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_notebooks import md,task1,task2
from notebook_enrichment import enrich_notebook


class NotebookMarkdownTests(unittest.TestCase):
    def test_heading_first_template_does_not_turn_prose_into_code(self):
        source=''.join(md('# Title\n        A normal paragraph.\n\n        ### Subsection\n        More prose.')['source'])
        self.assertEqual(source,'# Title\nA normal paragraph.\n\n### Subsection\nMore prose.')

    def test_relative_indentation_inside_fenced_code_is_preserved(self):
        source=''.join(md('# Title\n        ```python\n        if ready:\n            work()\n        ```')['source'])
        self.assertIn('if ready:\n    work()',source)
        self.assertIn('\n```python\n',source)

    def test_generated_prose_and_subheadings_are_not_indented_and_links_resolve(self):
        for name,build in [('task1_eda',task1),('task2_preprocessing',task2)]:
            cells=build()
            for index,cell in enumerate(cells): cell['id']=f'{name}-{index:03d}'
            cells=enrich_notebook(name,cells)
            sources=[''.join(cell['source']) for cell in cells if cell['cell_type']=='markdown']
            for source in sources:
                self.assertIsNone(re.search(r'(?m)^ {4,}\S',source),name+': unintended indented Markdown')
            all_text='\n'.join(sources)
            anchors=set(re.findall(r'<a id="([^"]+)"',all_text))
            links=set(re.findall(r'\]\(#([^)]+)\)',all_text))
            self.assertTrue(links)
            self.assertTrue(links.issubset(anchors),links-anchors)

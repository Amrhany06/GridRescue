"""Extraction must retain all dates, original tokens, and only requested counties."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from extract_counties import extract_file


class CountyExtractionTests(unittest.TestCase):
    def test_all_dates_and_missing_tokens_survive_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source.csv', root / 'selected.csv'
            source.write_text('fips_code,county,state,customers_out,run_start_time\n'
                              '06037,Los Angeles,California,,2020-01-01 00:00:00\n'
                              '01001,Autauga,Alabama,50,2020-07-01 00:00:00\n'
                              '06037,Los Angeles,California,200,2020-12-31 23:45:00\n', encoding='utf-8')
            result = extract_file(source, target, {'06037'})
            self.assertEqual(result['parsed_rows'], 3)
            self.assertEqual(result['selected_rows'], 2)
            with target.open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([r['customers_out'] for r in rows], ['', '200'])
            self.assertEqual([r['run_start_time'] for r in rows], ['2020-01-01 00:00:00', '2020-12-31 23:45:00'])

    def test_bad_column_count_fails_instead_of_dropping_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.csv'
            source.write_text('fips_code,county,state,customers_out,run_start_time\n06037,too,few\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                extract_file(source, root / 'selected.csv', {'06037'})

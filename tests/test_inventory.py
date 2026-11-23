"""File-integrity regression checks; no Spark or third-party dependencies."""
import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from inventory import scan_file


class InventoryTests(unittest.TestCase):
    def scan_bytes(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.csv"
            path.write_bytes(payload)
            return scan_file(path)

    def test_header_is_excluded_and_final_newline_is_not_an_extra_row(self):
        result = self.scan_bytes(b"header\na\nb\n")
        self.assertEqual(result["physical_lines_including_header"], 3)
        self.assertEqual(result["physical_data_lines"], 2)
        self.assertEqual(result["newline_bytes"], 3)
        self.assertEqual(result["bytes"], 11)
        self.assertTrue(result["ends_with_newline"])
        self.assertIsNone(result["row_count"])

    def test_unterminated_last_line_is_counted(self):
        result = self.scan_bytes(b"header\na")
        self.assertEqual(result["physical_lines_including_header"], 2)
        self.assertEqual(result["physical_data_lines"], 1)
        self.assertEqual(result["newline_bytes"], 1)
        self.assertFalse(result["ends_with_newline"])

    def test_empty_file_has_no_header_or_negative_data_count(self):
        result = self.scan_bytes(b"")
        self.assertEqual(result["physical_lines_including_header"], 0)
        self.assertEqual(result["physical_data_lines"], 0)
        self.assertEqual(result["bytes"], 0)
        self.assertEqual(result["sha256"], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertFalse(result["ends_with_newline"])

    def test_sha256_covers_all_original_bytes(self):
        # Standard SHA256 test vector, independent of the scanner's implementation.
        result = self.scan_bytes(b"abc")
        self.assertEqual(result["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(result["bytes"], 3)
        self.assertEqual(result["physical_data_lines"], 0)

    def test_quoted_newline_is_physical_line_not_csv_record(self):
        payload = b'header\n"a\nb"\n'
        result = self.scan_bytes(payload)
        self.assertEqual(result["physical_data_lines"], 2)
        self.assertEqual(result["double_quote_bytes"], 2)
        self.assertIsNone(result["row_count"])
        self.assertEqual(len(list(csv.reader(io.StringIO(payload.decode())))) - 1, 1)

    def test_chunk_boundary_retains_final_byte_and_all_newlines(self):
        payload = b"header\n" + b"x" * (8 * 1024 * 1024) + b"\na"
        result = self.scan_bytes(payload)
        self.assertEqual(result["physical_data_lines"], 2)
        self.assertEqual(result["physical_lines_including_header"], 3)
        self.assertEqual(result["newline_bytes"], 2)
        self.assertEqual(result["bytes"], 8 * 1024 * 1024 + 9)
        self.assertFalse(result["ends_with_newline"])


if __name__ == "__main__":
    unittest.main()

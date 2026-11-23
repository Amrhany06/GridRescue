"""Guard source selection so full development audits cannot open held-out 2022."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from full_source_audit import development_sources


class FullAuditSourceTests(unittest.TestCase):
    def test_root_sources_are_used_and_held_out_file_is_never_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for year in range(2018, 2023):
                (root / f"eaglei_outages_{year}.csv").touch()
            selected = development_sources(root)
            self.assertEqual([p.name for p in selected], [
                "eaglei_outages_2018.csv", "eaglei_outages_2019.csv",
                "eaglei_outages_2020.csv", "eaglei_outages_2021.csv"])
            self.assertTrue(all(p.parent == root for p in selected))

    def test_canonical_raw_location_takes_precedence_over_root_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "data" / "raw"
            canonical.mkdir(parents=True)
            for year in range(2018, 2022):
                (root / f"eaglei_outages_{year}.csv").touch()
                (canonical / f"eaglei_outages_{year}.csv").touch()
            selected = development_sources(root)
            self.assertEqual(len(selected), 4)
            self.assertTrue(all(p.parent == canonical for p in selected))

    def test_missing_development_year_fails_instead_of_using_2022(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for year in [2018, 2019, 2020, 2022]:
                (root / f"eaglei_outages_{year}.csv").touch()
            with self.assertRaises(FileNotFoundError):
                development_sources(root)


if __name__ == "__main__":
    unittest.main()

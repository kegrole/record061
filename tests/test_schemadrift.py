import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schemadrift.columns import read_table
from schemadrift.compare import compare_tables
from schemadrift.normalize import normalize_name
from schemadrift.rename import edit_distance, similarity


V1_CSV = """order_id,amount,currency,region,qty,customer_name,note,legacy_code,created_at,gross_amount,deleted_flag
000123,"1,234.50",CNY,华东,3,张三,1,X-1,2026-01-02 10:00:00,100.00,
000124,99.00,CNY,华北,1,李四,2,X-2,2026-01-03 10:00:00,200.00,
000125,10.50,USD,华南,7,王五,3,X-3,2026-01-04 10:00:00,300.00,
"""

V2_CSV = """order_id,amount,tax_rate,region,currency,qty,customer name,note,created_ts,gross_amount_cny,deleted_flag
000123,"1,234.50",0.08,华东,CNY,3,张三,待补充,2026-01-02 10:00:00,100.00,
000124,99.00,0.08,华北,CNY,1,李四,待补充,2026-01-03 10:00:00,200.00,
000123,"1,234.50",0.08,华东,CNY,3,张三,待补充,2026-01-02 10:00:00,100.00,
"""


class SchemaDriftTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_path = Path(self.temp_dir.name) / "v1.csv"
        self.new_path = Path(self.temp_dir.name) / "v2.csv"
        self.old_path.write_text(V1_CSV, encoding="utf-8")
        self.new_path.write_text(V2_CSV, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def report(self, old_path=None, new_path=None, threshold=0.6):
        old_table = read_table(str(old_path or self.old_path))
        new_table = read_table(str(new_path or self.new_path))
        return compare_tables(old_table, new_table, threshold)

    def changes_by_type(self, report, change_type):
        return [change for change in report["changes"] if change["change"] == change_type]

    def column_type_map(self, report, version):
        return {column["name"]: column["type"] for column in report[f"{version}_columns"]}

    def test_01_demo_fixtures_match_required_literal_content(self):
        self.assertEqual((ROOT / "demo" / "v1.csv").read_text(encoding="utf-8"), V1_CSV)
        self.assertEqual((ROOT / "demo" / "v2.csv").read_text(encoding="utf-8"), V2_CSV)

    def test_02_change_list_has_exact_six_changes_and_distribution(self):
        report = self.report()
        counts = {name: 0 for name in ("added", "removed", "renamed", "type_changed", "reordered")}
        for change in report["changes"]:
            counts[change["change"]] += 1
        self.assertEqual(len(report["changes"]), 6)
        self.assertEqual(counts, {
            "added": 1,
            "removed": 1,
            "renamed": 2,
            "type_changed": 1,
            "reordered": 1,
        })

    def test_03_added_and_removed_evidence(self):
        report = self.report()
        added = self.changes_by_type(report, "added")
        removed = self.changes_by_type(report, "removed")
        self.assertEqual(added, [{
            "change": "added",
            "field": "tax_rate",
            "evidence": {"position": 2, "type": "float"},
        }])
        self.assertEqual(removed, [{
            "change": "removed",
            "field": "legacy_code",
            "evidence": {"position": 7, "type": "string"},
        }])

    def test_04_renames_and_similarity(self):
        report = self.report()
        renamed = self.changes_by_type(report, "renamed")
        self.assertEqual(renamed, [
            {
                "change": "renamed",
                "field": "created_at",
                "evidence": {
                    "old_name": "created_at",
                    "new_name": "created_ts",
                    "similarity": 0.8,
                },
            },
            {
                "change": "renamed",
                "field": "gross_amount",
                "evidence": {
                    "old_name": "gross_amount",
                    "new_name": "gross_amount_cny",
                    "similarity": 0.75,
                },
            },
        ])
        self.assertEqual(edit_distance("created_at", "created_ts"), 2)
        self.assertEqual(similarity("created_at", "created_ts"), 0.8)
        self.assertEqual(edit_distance("gross_amount", "gross_amount_cny"), 4)
        self.assertEqual(similarity("gross_amount", "gross_amount_cny"), 0.75)

    def test_05_note_type_changed(self):
        report = self.report()
        self.assertEqual(self.changes_by_type(report, "type_changed"), [{
            "change": "type_changed",
            "field": "note",
            "evidence": {"old_type": "integer", "new_type": "string"},
        }])

    def test_06_reordered_pair_is_currency_region(self):
        report = self.report()
        reordered = self.changes_by_type(report, "reordered")
        self.assertEqual(len(reordered), 1)
        self.assertEqual(reordered[0]["evidence"]["columns"], [["currency", "region"]])

    def test_07_insertion_and_removal_do_not_create_extra_reorders(self):
        report = self.report()
        reordered = self.changes_by_type(report, "reordered")
        self.assertEqual(len(reordered), 1)
        self.assertEqual(reordered[0]["evidence"]["columns"], [["currency", "region"]])
        self.assertEqual(report["summary"]["reordered"], 1)

    def test_08_spaced_customer_name_normalizes_to_common_column(self):
        report = self.report()
        self.assertEqual(normalize_name("customer name"), normalize_name("customer_name"))
        renamed_fields = [change["field"] for change in self.changes_by_type(report, "renamed")]
        self.assertNotIn("customer_name", renamed_fields)
        self.assertNotIn("customer name", renamed_fields)
        self.assertEqual(report["v2_columns"][6], {
            "name": "customer name",
            "type": "string",
            "position": 6,
        })

    def test_09_required_v1_type_inference(self):
        report = self.report()
        v1_types = self.column_type_map(report, "v1")
        self.assertEqual(v1_types["amount"], "float")
        self.assertEqual(v1_types["gross_amount"], "float")
        self.assertEqual(v1_types["note"], "integer")
        self.assertEqual(v1_types["deleted_flag"], "null")

    def test_10_primary_key_remains_text_with_leading_zero(self):
        report = self.report()
        self.assertEqual(self.column_type_map(report, "v1")["order_id"], "text")
        self.assertEqual(self.column_type_map(report, "v2")["order_id"], "text")

    def test_11_v2_note_is_string_and_created_timestamp_is_date(self):
        report = self.report()
        v2_types = self.column_type_map(report, "v2")
        self.assertEqual(v2_types["note"], "string")
        self.assertEqual(v2_types["created_ts"], "date")

    def test_12_duplicate_primary_key_reports_value(self):
        report = self.report()
        self.assertEqual(report["duplicate_primary_keys"], {
            "v1": [],
            "v2": ["000123"],
        })
        self.assertEqual(report["summary"]["duplicate_primary_keys"], 1)

    def test_13_report_shapes_and_threshold(self):
        report = self.report()
        for column in report["v1_columns"] + report["v2_columns"]:
            self.assertEqual(set(column.keys()), {"name", "type", "position"})
        for change in report["changes"]:
            self.assertEqual(set(change.keys()), {"change", "field", "evidence"})
            self.assertIsInstance(change["evidence"], dict)
        self.assertEqual(set(report["summary"].keys()), {
            "added",
            "removed",
            "renamed",
            "type_changed",
            "reordered",
            "duplicate_primary_keys",
            "threshold",
        })
        self.assertEqual(report["summary"]["threshold"], 0.6)

    def test_14_created_at_match_leaves_one_rename_and_five_changes(self):
        variant_path = Path(self.temp_dir.name) / "v2-created-at.csv"
        variant_path.write_text(V2_CSV.replace("created_ts", "created_at"), encoding="utf-8")
        report = self.report(new_path=variant_path)
        renamed = self.changes_by_type(report, "renamed")
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0]["field"], "gross_amount")
        self.assertEqual(len(report["changes"]), 5)
        self.assertEqual(len(self.changes_by_type(report, "type_changed")), 1)
        self.assertEqual(self.changes_by_type(report, "type_changed")[0]["field"], "note")

    def test_15_numeric_note_removes_type_change_and_leaves_five_changes(self):
        variant_path = Path(self.temp_dir.name) / "v2-numeric-note.csv"
        variant_path.write_text(V2_CSV.replace("待补充", "4"), encoding="utf-8")
        report = self.report(new_path=variant_path)
        self.assertEqual(len(self.changes_by_type(report, "type_changed")), 0)
        self.assertEqual(len(report["changes"]), 5)
        self.assertEqual(report["summary"], {
            "added": 1,
            "removed": 1,
            "renamed": 2,
            "type_changed": 0,
            "reordered": 1,
            "duplicate_primary_keys": 1,
            "threshold": 0.6,
        })

    def test_16_cli_succeeds_and_report_is_byte_stable(self):
        first_output = Path(self.temp_dir.name) / "first.json"
        second_output = Path(self.temp_dir.name) / "second.json"
        command = [
            sys.executable,
            "-m",
            "schemadrift.cli",
            "--old",
            str(self.old_path),
            "--new",
            str(self.new_path),
            "--threshold",
            "0.6",
            "--out",
            str(first_output),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.count(os.linesep), 1)
        self.assertIn("changes=6", completed.stdout)
        self.assertIn("renamed=2", completed.stdout)
        self.assertIn("duplicate_primary_keys=1", completed.stdout)

        command[-1] = str(second_output)
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertEqual(first_output.read_bytes(), second_output.read_bytes())
        report = json.loads(first_output.read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["threshold"], 0.6)

    def test_17_multiple_adjacent_inversions_remain_one_reordered_change(self):
        old_csv = Path(self.temp_dir.name) / "multi-old.csv"
        new_csv = Path(self.temp_dir.name) / "multi-new.csv"
        old_csv.write_text("order_id,a,b,c\n1,one,two,three\n", encoding="utf-8")
        new_csv.write_text("order_id,c,b,a\n1,three,two,one\n", encoding="utf-8")
        report = self.report(old_path=old_csv, new_path=new_csv)
        reordered = self.changes_by_type(report, "reordered")
        self.assertEqual(len(reordered), 1)
        self.assertEqual(reordered[0]["evidence"]["columns"], [["a", "b"], ["b", "c"]])
        self.assertEqual(report["summary"]["reordered"], 1)

    def test_18_similarity_uses_half_up_rounding_to_four_decimals(self):
        self.assertEqual(similarity("abcde", "abcX"), 0.6)
        self.assertEqual(similarity("abcdefgh", "abcXefgh"), 0.875)
        self.assertEqual(edit_distance("abcdefgh", "abcXefgh"), 1)
        self.assertEqual(similarity("abcdefghijklmnop", "Xbcdefghijklmnop"), 0.9375)


if __name__ == "__main__":
    unittest.main()

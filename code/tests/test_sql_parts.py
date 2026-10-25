"""SQL loader pieces: row normalization, line locators and coverage rules (ADR 0014)."""

import json
import unittest

import _path  # noqa: F401  (puts code/ on sys.path)

from ghostaudit.loaders import sql


class Rows(unittest.TestCase):
    def test_generic_rows_flatten_record_json_and_its_document(self):
        row = {
            "origin_system": "search_service",
            "collection_name": "search_documents",
            "updated_at": "2026-09-01T00:00:00Z",
            "record_json": json.dumps(
                {"email": "x", "nested": {"a": 1}, "document": {"phone": "1"}}
            ),
        }
        system, _cat, fields, observed = sql._generic_row(row, "2026-09-02T00:00:00Z")
        self.assertEqual(system, "search_service")
        self.assertEqual(fields, {"email": "x", "phone": "1", "collection": "search_documents"})
        self.assertEqual(observed, "2026-09-01T00:00:00Z")

    def test_typed_rows_take_the_first_iso_time_else_the_capture_time(self):
        typed = ("account_service", None)
        row = {"resource_id": "account_1", "updated_at": "2026-08-01T10:00:00Z"}
        self.assertEqual(
            sql._typed_row(row, typed, "2026-09-01T00:00:00Z")[3], "2026-08-01T10:00:00Z"
        )
        row = {"resource_id": "account_1", "updated_at": "yesterday"}
        self.assertEqual(
            sql._typed_row(row, typed, "2026-09-01T00:00:00Z")[3], "2026-09-01T00:00:00Z"
        )

    def test_insert_lines_map_each_resource_to_its_first_insert(self):
        text = (
            "CREATE TABLE t (x);\n"
            "INSERT INTO t VALUES ('account_1', 1);\n"
            "INSERT INTO t VALUES ('account_1', 2);"
        )
        self.assertEqual(sql._insert_lines(text), {("t", "account_1"): 2})


class CoverageRules(unittest.TestCase):
    def test_inventory_scope_uses_its_own_time_and_only_scoped_systems(self):
        scope = {"account_service": "2026-09-05T00:00:00Z"}
        cov = sql._coverage(
            "f",
            "2026-09-06T00:00:00Z",
            "customer_profiles",
            ("account_service", None),
            scope,
            set(),
        )
        self.assertEqual(
            [(c.captured_at, c.system_id) for c in cov],
            [("2026-09-05T00:00:00Z", "account_service")],
        )
        self.assertEqual(sql._coverage("f", "t", "x", ("search_service", None), scope, set()), [])

    def test_without_scope_a_typed_table_covers_its_system_and_a_generic_one_what_it_lists(self):
        cov = sql._coverage("f", "t", "customer_profiles", ("account_service", None), {}, set())
        self.assertEqual([c.system_id for c in cov], ["account_service"])
        cov = sql._coverage("f", "t", "records", None, {}, {"b_service", "a_service"})
        self.assertEqual([c.system_id for c in cov], ["a_service", "b_service"])


if __name__ == "__main__":
    unittest.main()

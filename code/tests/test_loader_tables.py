"""Loader tables: content-signature dispatch order and the generic state signals (ADR 0014)."""

import json
import unittest

import _path  # noqa: F401  (puts code/ on sys.path)

from ghostaudit import loaders
from ghostaudit.loaders.common import exposed_with_free_emails, state_from_fields


class Signatures(unittest.TestCase):
    def test_binary_magic_wins_before_text(self):
        self.assertEqual(loaders.sniff(b"%PDF-1.7 ..."), "pdf")
        self.assertEqual(loaders.sniff(b"\x89PNG\r\n..."), "png")

    def test_json_shapes_in_order(self):
        def sniff(obj):
            return loaders.sniff(json.dumps(obj).encode())

        self.assertEqual(sniff({"service_exports": {}, "snapshots": []}), "json:service_exports")
        self.assertEqual(sniff({"snapshots": []}), "json:snapshots")
        self.assertEqual(sniff({"records": []}), "json:records")
        with self.assertRaises(loaders.UnknownSignature):
            sniff({"something": 1})
        with self.assertRaises(loaders.UnknownSignature):
            loaders.sniff(b"[1, 2]")

    def test_unknown_text_and_bad_bytes_are_hard_errors(self):
        with self.assertRaises(loaders.UnknownSignature):
            loaders.sniff(b"hello world\n")
        with self.assertRaises(loaders.UnknownSignature):
            loaders.sniff(b"\xff\xfe\x00")
        with self.assertRaises(loaders.UnknownSignature):
            loaders.sniff(b"{not json")


class States(unittest.TestCase):
    def test_explicit_absence_signals(self):
        for fields in (
            {"http_status": 404},
            {"status_code": "404"},
            {"rows": 0},
            {"result": "NOT_FOUND"},
            {"total_hits": "0"},
            {"archive_present": False},
        ):
            self.assertEqual(state_from_fields(fields), "ABSENT", fields)

    def test_absence_beats_flags_and_flags_map_to_states(self):
        self.assertEqual(state_from_fields({"rows": "0", "enabled": "true"}), "ABSENT")
        self.assertEqual(state_from_fields({"restore_allowed": 1}), "RESTORABLE")
        self.assertEqual(state_from_fields({"restore_allowed": "false"}), "BLOCKED")
        self.assertEqual(state_from_fields({"enabled": True}), "ACTIVE")
        self.assertEqual(state_from_fields({"enabled": "0"}), "DISABLED")
        self.assertEqual(state_from_fields({"anything": "x"}), "PRESENT")

    def test_an_email_in_free_text_counts_as_exposed(self):
        pii, free = exposed_with_free_emails({"note": "write to someone@example.org please"})
        self.assertIn("email", pii)
        self.assertEqual(free, ["someone@example.org"])


if __name__ == "__main__":
    unittest.main()

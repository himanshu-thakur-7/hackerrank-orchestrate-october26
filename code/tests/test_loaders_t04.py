"""T04 loaders: content-signature dispatch, handover txt, service-export JSON, readback logs.

Fixtures in fixtures/ are verbatim excerpts of real dataset files (the JSON one re-serialised from
real records). Expected Observations were read off the fixture text by hand.
"""

import unittest
from pathlib import Path
from _path import DATA  # noqa: F401
from ghostaudit import loaders
from ghostaudit.store import Observation

FIX = Path(__file__).resolve().parent / "fixtures"


def load(name, file_id="F1", captured_at="2026-10-01T12:00:00Z"):
    return loaders.load_bytes(file_id, captured_at, (FIX / name).read_bytes())


def by_res(result):
    return {(o.system_id, o.resource_id): o for o in result.observations}


class Sniffing(unittest.TestCase):
    def test_dispatch_ignores_file_names(self):
        raw = (FIX / "handover_excerpt.txt").read_bytes()
        self.assertEqual(loaders.sniff(raw), "txt:handover")
        self.assertEqual(loaders.sniff((FIX / "readback_excerpt.log").read_bytes()), "log:readback")
        self.assertEqual(
            loaders.sniff((FIX / "service_export_excerpt.json").read_bytes()),
            "json:service_exports",
        )
        self.assertEqual(loaders.sniff(b"%PDF-1.4 ..."), "pdf")

    def test_unknown_signature_is_a_hard_error_with_a_precise_message(self):
        with self.assertRaises(loaders.UnknownSignature) as cm:
            loaders.load_bytes("F9", "2026-01-01T00:00:00Z", b'{"something": "else"}')
        self.assertIn("F9", str(cm.exception))
        self.assertIn("JSON object with keys ['something']", str(cm.exception))
        with self.assertRaises(loaders.UnknownSignature):
            loaders.load_bytes(
                "F8", "2026-01-01T00:00:00Z", b"just some prose\nwithout structure\n"
            )


class Handover(unittest.TestCase):
    def test_rows_become_observations_with_category_state_and_owner(self):
        r = load("handover_excerpt.txt")
        o = by_res(r)
        self.assertEqual(
            o[("analytics_platform", "analytics_2034")],
            Observation(
                "F1",
                "2026-10-01T12:00:00Z",
                "analytics_platform",
                "analytics_2034",
                "handover",
                "PRESENT",
                category="ANALYTICS_PROFILE",
                pii_fields=("email",),
                identifiers=("novak.tomasz@icloud.com",),
                locator="line 5",
                attrs=(("status", "IDENTIFIABLE"),),
            ),
        )
        self.assertEqual(o[("analytics_platform", "analytics_6830")].pii_fields, ())
        self.assertEqual(o[("analytics_platform", "analytics_6830")].identifiers, ())
        self.assertEqual(o[("backup_service", "backup_3870")].state, "RESTORABLE")
        self.assertEqual(o[("support_platform", "support_4218")].category, "SUPPORT_ATTACHMENT")
        self.assertEqual(len(r.observations), 4)
        self.assertEqual(r.coverage, [])  # a shift checklist is not exhaustive
        self.assertEqual([u.locator for u in r.unattributed], ["line 6"])


class ServiceExport(unittest.TestCase):
    def test_each_probed_resource_becomes_one_observation(self):
        r = load("service_export_excerpt.json")
        o = by_res(r)
        self.assertEqual(
            o[("account_service", "account_3136")],
            Observation(
                "F1",
                "2026-09-15T09:31:40Z",
                "account_service",
                "account_3136",
                "account_service.profile_lookups",
                "ABSENT",
                locator="line 10",
                attrs=(("status_code", "404"),),
            ),
        )
        a = o[("account_service", "account_5334")]
        self.assertEqual(
            (a.state, a.pii_fields, a.identifiers, a.locator),
            ("PRESENT", ("email",), ("keiko.nakamura@gmail.com",), "line 22"),
        )
        an = o[("analytics_platform", "analytics_5208")]
        self.assertEqual(
            (an.state, an.pii_fields, an.identifiers, an.observed_at),
            ("PRESENT", ("email",), ("noah.f438085@outlook.com",), "2026-09-15T11:38:32Z"),
        )
        b = o[("backup_service", "backup_3120")]
        self.assertEqual(
            (b.state, b.identifiers, b.pii_fields, b.locator),
            ("BLOCKED", ("user_26",), (), "line 47"),
        )
        s = o[("search_service", "search_1993")]
        self.assertEqual(
            (s.state, s.pii_fields, s.identifiers, s.locator, s.observed_at),
            (
                "PRESENT",
                ("email",),
                ("noah.f438085@outlook.com",),
                "line 63",
                "2026-09-15T09:14:18Z",
            ),
        )
        self.assertEqual(len(r.observations), 5)
        self.assertEqual(r.coverage, [])  # a probe list is not exhaustive
        self.assertEqual([u.locator for u in r.unattributed], ["line 10"])


class Readback(unittest.TestCase):
    def test_trace_join_attaches_the_lookup_key_to_the_completed_record(self):
        r = load("readback_excerpt.log")
        o = by_res(r)
        self.assertEqual(
            o[("account_service", "account_2064")],
            Observation(
                "F1",
                "2026-09-26T07:49:50Z",
                "account_service",
                "account_2064",
                "account_service.readback",
                "ABSENT",
                identifiers=("charlotte.wright@outlook.com",),
                locator="line 3",
                attrs=(("http_status", "404"), ("rows", "0")),
            ),
        )
        f = o[("integration_service", "data_flow_4713")]
        self.assertEqual(
            (f.state, f.identifiers, f.pii_fields, f.locator),
            ("DISABLED", ("user_49",), (), "line 5"),
        )
        b = o[("backup_service", "backup_7809")]
        self.assertEqual((b.state, b.identifiers, b.locator), ("BLOCKED", ("user_49",), "line 7"))
        s = o[("search_service", "search_459")]
        self.assertEqual(
            (s.state, s.pii_fields, s.identifiers, s.observed_at),
            ("PRESENT", ("email",), ("tunde.c692281@zoho.com",), "2026-09-26T10:38:56Z"),
        )
        self.assertEqual(len(r.observations), 4)
        self.assertEqual(r.unparsed, [])


class SniffCollision(unittest.TestCase):
    def test_observability_logfmt_with_lookup_keys_is_not_readback(self):
        # real excerpt: logfmt service events carry instance=/pod=/region= before trace_id
        raw = (FIX / "observability_logfmt_excerpt.log").read_bytes()
        self.assertEqual(loaders.sniff(raw), "log:observability")
        evidence_30_style = (
            b"2026-05-14T11:58:42Z level=DEBUG service=account_service instance=account-6 "
            b"pod=account-3740 "
            b"region=ap-south-1 trace_id=tr-9048368 event=profile_lookup_started "
            b'lookup_key="lars.e5052@outlook.com" attempt=1\n'
        )
        self.assertEqual(loaders.sniff(evidence_30_style), "log:observability")

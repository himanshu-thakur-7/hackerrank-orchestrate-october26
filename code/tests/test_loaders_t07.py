"""T07 loader: observability logs, all seven dialects (logfmt, JSON-after-timestamp, syslog,
bracketed, pipe, cloud-runtime, support replica). Fixtures are verbatim line excerpts:
  observability_logfmt_excerpt.log   evidence_01 lines 1-6
  obs_logfmt_traces_excerpt.log      evidence_01 lines 11, 15, 43, 53, 92
  obs_json_excerpt.log               evidence_06 lines 2, 4, 19, 48, 50
  obs_syslog_excerpt.log             evidence_11 lines 1-6
  obs_bracket_excerpt.log            evidence_16 lines 1-4, 11
  obs_pipe_excerpt.log               evidence_21 lines 3, 7, 59, 63
  obs_cloud_excerpt.log              evidence_25 lines 1, 2, 10, 12
  obs_support_replica_excerpt.log    evidence_61 lines 1-10
"""

import unittest
from pathlib import Path
from _path import DATA  # noqa: F401
from ghostaudit import loaders
from ghostaudit.store import Observation

FIX = Path(__file__).resolve().parent / "fixtures"
HASH = "44a65154bfd8e408852578fbd76813d094d1944f255ac1769ee81ba90492f10e"


def load(name, fid="F1", cap="2026-09-30T12:00:00Z"):
    return loaders.load_bytes(fid, cap, (FIX / name).read_bytes())


def by_res(r):
    return {o.resource_id: o for o in r.observations}


class Dispatch(unittest.TestCase):
    def test_every_dialect_sniffs_as_observability_by_content(self):
        for name in (
            "observability_logfmt_excerpt.log",
            "obs_logfmt_traces_excerpt.log",
            "obs_json_excerpt.log",
            "obs_syslog_excerpt.log",
            "obs_bracket_excerpt.log",
            "obs_pipe_excerpt.log",
            "obs_cloud_excerpt.log",
            "obs_support_replica_excerpt.log",
        ):
            self.assertEqual(loaders.sniff((FIX / name).read_bytes()), "log:observability", name)
            self.assertEqual(load(name).signature, "log:observability")

    def test_a_line_in_no_known_dialect_is_reported_unparsed_not_skipped(self):
        raw = (
            FIX / "obs_syslog_excerpt.log"
        ).read_bytes() + b"2026-08-22T10:52:00Z ??? something else entirely\n"
        r = loaders.load_bytes("F1", "2026-09-30T12:00:00Z", raw)
        self.assertEqual(
            [(u.locator, u.reason) for u in r.unparsed],
            [("line 7", "line matches no observability dialect")],
        )

    def test_logs_are_query_traces_so_they_never_emit_coverage(self):
        for name in ("obs_json_excerpt.log", "obs_support_replica_excerpt.log"):
            self.assertEqual(load(name).coverage, [])


class Logfmt(unittest.TestCase):
    def test_lookalike_match_key_is_kept_verbatim_and_does_not_become_the_real_email(self):
        r = load("observability_logfmt_excerpt.log", cap="2026-09-15T11:59:39Z")
        self.assertEqual(
            r.observations,
            [
                Observation(
                    "F1",
                    "2026-09-15T08:51:57Z",
                    "search_service",
                    "search_1874",
                    "search_service.log",
                    "PRESENT",
                    identifiers=("g.silva76.jr@gmail.com",),
                    locator="line 6",
                    attrs=(
                        ("event", "index_query_completed"),
                        ("index", "customer_directory_v3"),
                        ("result", "hit"),
                        ("shard", "2"),
                        ("took_ms", "17"),
                    ),
                )
            ],
        )
        self.assertEqual(r.unparsed, [])

    def test_trace_join_pii_scan_restore_risk_and_hash_correlation(self):
        o = by_res(load("obs_logfmt_traces_excerpt.log", cap="2026-09-15T11:59:39Z"))
        self.assertEqual(
            o["support_9553"],
            Observation(
                "F1",
                "2026-09-15T11:51:08Z",
                "support_platform",
                "support_9553",
                "support_platform.log",
                "PRESENT",
                pii_fields=("email",),
                identifiers=("e.varga90@yahoo.com",),
                locator="line 2",
                attrs=(("detector", "direct_identifier"), ("event", "message_pii_scan")),
            ),
        )
        self.assertEqual(
            o["backup_3245"],
            Observation(
                "F1",
                "2026-09-15T11:54:41Z",
                "backup_service",
                "backup_3245",
                "backup_service.log",
                "RESTORABLE",
                identifiers=("leonie.g9352@outlook.com",),
                locator="line 4",
                attrs=(
                    ("deletion_block", "false"),
                    ("eligible", "true"),
                    ("event", "restore_candidate_evaluated"),
                ),
            ),
        )
        self.assertEqual(
            o["analytics_9914"],
            Observation(
                "F1",
                "2026-09-15T11:58:26Z",
                "analytics_platform",
                "analytics_9914",
                "analytics_platform.log",
                "PRESENT",
                identifiers=(HASH,),
                locator="line 5",
                attrs=(
                    ("email_opt_in", "true"),
                    ("event", "contact_lookup_completed"),
                    ("rows", "1"),
                ),
            ),
        )


class OtherDialects(unittest.TestCase):
    def test_json_after_timestamp(self):
        o = by_res(load("obs_json_excerpt.log"))
        self.assertEqual(
            o["account_6633"],
            Observation(
                "F1",
                "2026-09-10T08:56:20Z",
                "account_service",
                "account_6633",
                "account_service.log",
                "PRESENT",
                identifiers=("collins.grace@icloud.com",),
                locator="line 2",
                attrs=(
                    ("duration_ms", "84"),
                    ("event", "profile_lookup_completed"),
                    ("http_status", "200"),
                    ("rows", "1"),
                ),
            ),
        )
        self.assertEqual(
            (o["data_flow_6846"].state, o["data_flow_6846"].identifiers), ("DISABLED", ("user_62",))
        )
        self.assertEqual(
            (o["backup_3933"].state, o["backup_3933"].identifiers, o["backup_3933"].locator),
            ("BLOCKED", ("user_62",), "line 5"),
        )

    def test_syslog(self):
        o = by_res(load("obs_syslog_excerpt.log"))
        self.assertEqual(
            o["account_1785"],
            Observation(
                "F1",
                "2026-08-22T10:51:17Z",
                "account_service",
                "account_1785",
                "account_service.log",
                "PRESENT",
                identifiers=("nana.b9576@outlook.com",),
                locator="line 3",
                attrs=(
                    ("duration_ms", "50"),
                    ("event", "profile_lookup_completed"),
                    ("http_status", "200"),
                    ("rows", "1"),
                ),
            ),
        )
        s = o["support_9309"]
        self.assertEqual(
            (s.state, s.pii_fields, s.identifiers, dict(s.attrs)["file"]),
            ("PRESENT", ("email",), ("joao-santos@proton.me",), "delivery_confirmation_94.pdf"),
        )

    def test_bracketed(self):
        r = load("obs_bracket_excerpt.log")
        o = by_res(r)
        self.assertEqual(
            o["account_7947"],
            Observation(
                "F1",
                "2026-07-28T05:51:21Z",
                "account_service",
                "account_7947",
                "account_service.log",
                "ABSENT",
                identifiers=("l.nascimento40@gmail.com",),
                locator="line 4",
                attrs=(
                    ("duration_ms", "70"),
                    ("event", "profile_lookup_completed"),
                    ("http_status", "404"),
                    ("rows", "0"),
                ),
            ),
        )
        self.assertEqual(
            (o["account_4289"].state, o["account_4289"].identifiers),
            ("PRESENT", ("erik.h9688@outlook.com",)),
        )
        self.assertEqual(len(r.observations), 2)

    def test_pipe_resource_id_lookup_key_is_not_an_identifier(self):
        r = load("obs_pipe_excerpt.log")
        o = by_res(r)
        self.assertEqual(
            o["analytics_257"],
            Observation(
                "F1",
                "2026-07-03T07:51:59Z",
                "analytics_platform",
                "analytics_257",
                "analytics_platform.log",
                "PRESENT",
                locator="line 2",
                attrs=(("direct_identifiers", "0"), ("event", "analytics_profile_read")),
            ),
        )
        self.assertEqual([u.locator for u in r.unattributed], ["line 2"])
        self.assertEqual(
            (
                o["legal_hold_4961"].system_id,
                o["legal_hold_4961"].state,
                o["legal_hold_4961"].identifiers,
            ),
            ("legal_service", "PRESENT", ("user_218",)),
        )

    def test_cloud_runtime_escaped_message(self):
        o = by_res(load("obs_cloud_excerpt.log"))
        self.assertEqual(o["search_021"].identifiers, ("mrios9507.jr@fastmail.com",))
        self.assertEqual(
            o["data_flow_2010"],
            Observation(
                "F1",
                "2026-06-08T09:51:18Z",
                "integration_service",
                "data_flow_2010",
                "integration_service.log",
                "ACTIVE",
                identifiers=("thabo.masuku@outlook.com",),
                locator="line 4",
                attrs=(
                    ("enabled", "true"),
                    ("event", "connector_heartbeat"),
                    ("last_run", "success"),
                    ("scheduler_registered", "true"),
                ),
            ),
        )

    def test_support_replica_lines_are_support_platform_records_in_a_replica_table(self):
        r = load("obs_support_replica_excerpt.log", cap="2026-09-17T22:00:19Z")
        got = [
            (o.resource_id, o.locator, o.system_id, o.table, o.state, o.identifiers)
            for o in r.observations
        ]
        self.assertEqual(
            got,
            [
                (
                    "support_4104",
                    "line 3",
                    "support_platform",
                    "support_replica.log",
                    "PRESENT",
                    ("customer4104@yahoo.com",),
                ),
                (
                    "support_002",
                    "line 5",
                    "support_platform",
                    "support_replica.log",
                    "PRESENT",
                    ("nadia.ionescu@yahoo.com",),
                ),
                (
                    "support_002",
                    "line 6",
                    "support_platform",
                    "support_replica.log",
                    "PRESENT",
                    ("nadia.ionescu@yahoo.com",),
                ),
                (
                    "support_7731",
                    "line 7",
                    "support_platform",
                    "attachment_preview.log",
                    "PRESENT",
                    (),
                ),
                (
                    "support_5914",
                    "line 8",
                    "support_platform",
                    "support_replica.log",
                    "PRESENT",
                    ("nadia.popescu@yahoo.com",),
                ),
            ],
        )
        self.assertEqual(dict(r.observations[2].attrs)["marker_found"], "false")
        self.assertEqual([u.locator for u in r.unattributed], ["line 7"])
        self.assertEqual(r.unparsed, [])


if __name__ == "__main__":
    unittest.main()

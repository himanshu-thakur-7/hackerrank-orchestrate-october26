"""T10 linking (ADR 0003, 0004, 0005): activity account candidates with ONE named window,
result<->status agreement, the pre-audit identity filter and global one-to-one elimination; unique
survivors only, ties logged; catalog links checked against their artifact; search source_resource_id
references.
Scenarios are synthetic copies of the sample situations named in each test."""

import unittest
from _world import DELETE, NEW, act, ob, request, resolver
from ghostaudit import linking, policy
from ghostaudit.engine import Engine
from ghostaudit.store import ActivityEvent, EvidenceFile, EvidenceStore
from _path import DATA


def req(case_id, email, reported_at, status="COMPLETE", audit_at="2026-09-15T12:00:00Z"):
    r = request(audit_at=audit_at, email=email, case_id=case_id)
    r.update(reported_at=reported_at, reported_status=status)
    return r


def delete(aid, at, account, result="SUCCESS"):
    return act(aid, at, "DELETE_RECORD", "account_service", account, result)


def link_row(aid, at, sys_, res, details):
    return ActivityEvent(
        aid, at, "LINK_RESOURCE_IDENTITY", "data_catalog", sys_, res, "SUCCESS", details
    )


def build(requests, activity=(), observations=(), files=(("F", "2026-09-01T00:00:00Z"),)):
    store = EvidenceStore(
        files=[EvidenceFile(f, f"evidence/x/{f}", "test", c) for f, c in files],
        observations=observations,
        activity=activity,
    )
    lk = linking.Linker(store, resolver(), requests, {q["case_id"]: DELETE for q in requests})
    return store, lk


class Window(unittest.TestCase):
    def test_the_window_is_one_named_constant(self):
        self.assertEqual(linking.ACCOUNT_DELETE_WINDOW_HOURS, (0.5, 1.5))

    def test_candidates_need_the_window_the_matching_result_and_a_pre_audit_time(self):
        # case_24 shape: activity_3599 SUCCESS 1.01 h before reported_at of a COMPLETE request
        q = req("case_1", NEW, "2026-09-02T12:00:00Z")
        _, lk = build(
            [q],
            [
                delete("a_in", "2026-09-02T10:59:00Z", "account_1"),
                delete("a_early", "2026-09-02T10:20:00Z", "account_2"),  # 1.67 h: outside
                delete("a_late", "2026-09-02T11:40:00Z", "account_3"),  # 0.33 h: outside
                delete("a_failed", "2026-09-02T11:00:00Z", "account_4", "FAILED"),
            ],
        )  # result mismatch
        a = lk.account("case_1")
        self.assertEqual((a.status, a.resource_id, a.activity_id), ("LINKED", "account_1", "a_in"))
        self.assertEqual([c.activity_id for c in a.candidates], ["a_in"])


class UniqueOnly(unittest.TestCase):
    def test_symmetric_pair_stays_tied_and_is_logged_with_its_candidates(self):
        # case_28 / case_29 shape: two requests, two deletes, nothing grounded tells them apart
        qs = [
            req("case_1", NEW, "2026-09-02T12:00:00Z"),
            req("case_2", "other@example.com", "2026-09-02T12:05:00Z"),
        ]
        _, lk = build(
            qs,
            [
                delete("a1", "2026-09-02T11:00:00Z", "account_1"),
                delete("a2", "2026-09-02T11:02:00Z", "account_2"),
            ],
        )
        for c in ("case_1", "case_2"):
            a = lk.account(c)
            self.assertEqual((a.status, a.resource_id), ("TIED", None))
            self.assertEqual(sorted(x.resource_id for x in a.survivors), ["account_1", "account_2"])
        self.assertEqual(lk.distribution(), {2: 2})

    def test_global_one_to_one_elimination(self):
        # case_2 has only a2 in its window; case_1 has a1 and a2, so a2 is taken and case_1 gets a1
        qs = [
            req("case_1", NEW, "2026-09-02T12:00:00Z"),
            req("case_2", "other@example.com", "2026-09-02T12:30:00Z"),
        ]
        _, lk = build(
            qs,
            [
                delete("a1", "2026-09-02T10:40:00Z", "account_1"),
                delete("a2", "2026-09-02T11:20:00Z", "account_2"),
            ],
        )
        self.assertEqual(
            (lk.account("case_1").resource_id, lk.account("case_2").resource_id),
            ("account_1", "account_2"),
        )

    def test_pre_audit_evidence_of_another_owner_drops_a_candidate_and_own_evidence_selects_it(
        self,
    ):
        qs = [req("case_1", NEW, "2026-09-02T12:00:00Z")]
        acts = [
            delete("a1", "2026-09-02T11:00:00Z", "account_1"),
            delete("a2", "2026-09-02T11:01:00Z", "account_2"),
        ]
        _, lk = build(
            qs,
            acts,
            [
                ob(
                    "F",
                    "2026-09-01T00:00:00Z",
                    "account_service",
                    "account_2",
                    ids=("other@example.com",),
                )
            ],
        )
        self.assertEqual(lk.account("case_1").resource_id, "account_1")
        _, lk = build(
            qs,
            acts,
            [ob("F", "2026-09-01T00:00:00Z", "account_service", "account_2", "ABSENT", ids=(NEW,))],
        )
        self.assertEqual(lk.account("case_1").resource_id, "account_2")

    def test_a_request_with_no_candidate_is_logged_not_guessed(self):
        _, lk = build([req("case_1", NEW, "2026-09-02T12:00:00Z")])
        self.assertEqual(
            (lk.account("case_1").status, lk.account("case_1").reason),
            ("NO_CANDIDATE", "no account delete in the window"),
        )


class Catalog(unittest.TestCase):
    def test_contradicted_catalog_link_is_rejected(self):
        # activity_4008: marketing_001 -> the subject, but the screen 7 minutes earlier shows
        # sj.park@naver.com
        store, lk = build(
            [req("case_1", NEW, "2026-09-16T12:00:00Z", audit_at="2026-09-17T09:20:00Z")],
            [
                link_row(
                    "activity_4008",
                    "2026-09-16T07:27:01Z",
                    "marketing_platform",
                    "marketing_001",
                    f"Data catalog linked marketing_001 (marketing_001) to {NEW} and user_1.",
                )
            ],
            [
                ob(
                    "E60",
                    "2026-09-16T07:20:00Z",
                    "marketing_platform",
                    "marketing_001",
                    ids=("sj.park@naver.com",),
                )
            ],
            files=(("E60", "2026-09-16T07:20:00Z"),),
        )
        view = store.as_of("2026-09-17T09:20:00Z")
        [c] = lk.catalog(view, resolver().resolve(NEW))
        self.assertEqual(
            (c.status, c.resource_id, c.artifact), ("CONTRADICTED", "marketing_001", "E60")
        )

    def test_catalog_link_with_no_artifact_is_unconfirmed(self):
        # activity_4007: object_19 -> the subject; the screen shows a file name and no person or id
        store, lk = build(
            [req("case_1", NEW, "2026-02-14T00:00:00Z", audit_at="2026-02-14T10:00:00Z")],
            [
                link_row(
                    "activity_4007",
                    "2026-02-13T08:07:01Z",
                    "object_storage",
                    "object_19",
                    f"Attachment catalog confirmed object_19 (x.pdf) belongs only to {NEW} and "
                    f"user_1.",
                )
            ],
        )
        [c] = lk.catalog(store.as_of("2026-02-14T10:00:00Z"), resolver().resolve(NEW))
        self.assertEqual(c.status, "UNCONFIRMED")


class EngineIntegration(unittest.TestCase):
    def engine(
        self, requests, activity=(), observations=(), files=(("F", "2026-09-15T11:00:00Z"),)
    ):
        store = EvidenceStore(
            files=[EvidenceFile(f, f"evidence/x/{f}", "test", c) for f, c in files],
            observations=observations,
            activity=activity,
        )
        lk = linking.Linker(store, resolver(), requests, {q["case_id"]: DELETE for q in requests})
        return Engine(
            store, resolver(), policy.Rules.from_csv(DATA / "deletion_rules.csv"), linker=lk
        )

    def test_activity_account_gets_a_cited_verification_from_identifier_free_evidence(self):
        # case_21 shape: evidence_92 shows account_6440 404 with no identifier; the activity window
        # links it
        q = req("case_1", NEW, "2026-09-02T12:00:00Z")
        e = self.engine(
            [q],
            [delete("activity_3601", "2026-09-02T11:00:00Z", "account_6440")],
            [
                ob("F", "2026-09-15T11:00:00Z", "account_service", "account_6440", "ABSENT"),
                ob(
                    "F",
                    "2026-09-15T11:00:00Z",
                    "security_service",
                    "audit_record_1",
                    ids=("user_1",),
                ),
            ],
        )
        a = e.assess(q, DELETE)
        self.assertEqual(
            (a.status, [(s["resource_id"], s["evidence_id"]) for s in a.steps]),
            ("COMPLETE", [("account_6440", "F"), ("audit_record_1", "F")]),
        )
        self.assertIn(
            "LINKED_ACCOUNT(account_6440 via activity_3601, 1.00 h before reported_at)", a.log
        )

    def test_absence_known_only_by_omission_cites_the_covering_file(self):
        # an activity-linked account that no file names: closed-world absence from the covering
        # snapshot
        from ghostaudit.store import Coverage

        q = req("case_1", NEW, "2026-09-02T12:00:00Z")
        store = EvidenceStore(
            files=[EvidenceFile("C", "evidence/x/C", "test", "2026-09-10T00:00:00Z")],
            coverage=[
                Coverage("C", "2026-09-10T00:00:00Z", "account_service", "customer_profiles")
            ],
            activity=[delete("activity_1", "2026-09-02T11:00:00Z", "account_77")],
        )
        lk = linking.Linker(store, resolver(), [q], {"case_1": DELETE})
        e = Engine(store, resolver(), policy.Rules.from_csv(DATA / "deletion_rules.csv"), linker=lk)
        self.assertEqual(
            [(s["resource_id"], s["evidence_id"]) for s in e.assess(q, DELETE).steps],
            [("account_77", "C")],
        )

    def test_search_source_reference_links_its_account(self):
        # case_06: evidence_57 search_001 (jonas.berg) carries source_resource_id account_006
        q = req("case_1", NEW, "2026-09-09T12:00:00Z", status="PARTIALLY_COMPLETE")
        e = self.engine(
            [q],
            observations=[
                ob(
                    "F",
                    "2026-09-09T10:00:00Z",
                    "search_service",
                    "search_001",
                    ids=(NEW,),
                    attrs=(("source_resource_id", "account_006"),),
                )
            ],
            files=(("F", "2026-09-09T10:00:00Z"),),
        )
        a = e.assess(q, DELETE)
        self.assertEqual(
            [(s["operation"], s["resource_id"]) for s in a.steps],
            [
                ("REPORT_REMAINING_RECORD", "search_001"),
                ("DELETE_RECORD", "search_001"),
                ("VERIFY_RECORD_ABSENT", "account_006"),
                ("VERIFY_RECORD_ABSENT", "search_001"),
            ],
        )

    def test_a_resource_seen_only_absent_before_the_request_is_a_previous_lifecycle(self):
        # case_17 / evidence_67: a March 404 lookup of the subject's email names account_6523 (the
        # earlier request's lifecycle); the August request must not verify it (ADR 0016). A
        # pre-request PRESENT sighting still counts: the data existed and may remain.
        q = req("case_1", NEW, "2026-08-22T12:00:00Z")
        q["requested_at"] = "2026-08-19T12:00:00Z"
        e = self.engine(
            [q],
            observations=[
                ob(
                    "F",
                    "2026-03-10T06:18:01Z",
                    "account_service",
                    "account_6523",
                    "ABSENT",
                    ids=(NEW,),
                    loc="line 3",
                ),
                ob(
                    "F", "2026-03-10T06:18:01Z", "search_service", "search_5", "PRESENT", ids=(NEW,)
                ),
                ob(
                    "F",
                    "2026-09-15T11:00:00Z",
                    "security_service",
                    "audit_record_1",
                    ids=("user_1",),
                ),
            ],
        )
        a = e.assess(q, DELETE)
        self.assertEqual(
            sorted({s["resource_id"] for s in a.steps}), ["audit_record_1", "search_5"]
        )
        self.assertIn(
            "STALE_LINK(account_service/account_6523: every link predates requested_at and shows "
            "it absent; "
            "latest F line 3 at 2026-03-10T06:18:01Z; ADR 0016)",
            a.log,
        )

    def test_contradicted_catalog_link_produces_no_step(self):
        q = req("case_1", NEW, "2026-09-16T12:00:00Z", audit_at="2026-09-17T09:20:00Z")
        e = self.engine(
            [q],
            [
                link_row(
                    "activity_4008",
                    "2026-09-16T07:27:01Z",
                    "marketing_platform",
                    "marketing_001",
                    f"Data catalog linked marketing_001 (marketing_001) to {NEW} and user_1.",
                )
            ],
            [
                ob(
                    "E60",
                    "2026-09-16T07:20:00Z",
                    "marketing_platform",
                    "marketing_001",
                    ids=("sj.park@naver.com",),
                )
            ],
            files=(("E60", "2026-09-16T07:20:00Z"),),
        )
        a = e.assess(q, DELETE)
        self.assertEqual(a.steps, [])
        self.assertTrue(
            any(l.startswith("REJECTED_LINK(activity_4008 marketing_001") for l in a.log), a.log
        )


if __name__ == "__main__":
    unittest.main()

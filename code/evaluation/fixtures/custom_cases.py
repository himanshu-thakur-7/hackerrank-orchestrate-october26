"""Custom evaluation cases: synthetic people, evidence and requests, applied to a dataset
overlay.

Every person, identifier and text here is invented. All dates are in 2027, after every real
audit_at, so the cases cannot change the 518 real rows (the runner checks that). Each case has a
HAND-WRITTEN expected row (status + ordered steps) and, where the point is an omission, the log line
that must explain it.

Decisions: ADR 0002 (all dates are in 2027, after every real audit_at).
"""

import hashlib


def _sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def L(ts, svc, trace, event, extra):
    """One observability log line (logfmt dialect)."""
    return (
        f"{ts} level=INFO service={svc} instance={svc}-1 pod={svc}-c0 region=eu-west-1 "
        f"trace_id={trace} event={event} {extra}"
    )


def lookup(ts, email, account, found=False, trace="tr-c"):
    """Observability lines of one account lookup: the started line, then found or not found."""
    return [
        L(
            ts,
            "account_service",
            trace,
            "profile_lookup_started",
            f'lookup_key="{email}" attempt=1',
        ),
        L(
            ts,
            "account_service",
            trace,
            "profile_lookup_completed",
            f"resource_id={account} rows=1 http_status=200"
            if found
            else f"resource_id={account} rows=0 http_status=404",
        ),
    ]


def search(ts, key, doc, trace="tr-s"):
    """Observability lines of one search-index query that hits document `doc`."""
    return [
        L(ts, "search_service", trace, "index_query_started", f'match_key="{key}" attempt=1'),
        L(
            ts,
            "search_service",
            trace,
            "index_query_completed",
            f"resource_id={doc} index=customer_directory_v3 result=hit shard=1 took_ms=9",
        ),
    ]


def person(uid, name, email, phone):
    """A user_identities.csv row for an invented person (the email hash is computed)."""
    return {
        "user_id": uid,
        "name": name,
        "email": email,
        "phone": phone,
        "email_hash": _sha(email),
        "updated_at": "2027-01-01T00:00:00Z",
    }


def request(
    cid,
    email,
    req,
    status,
    rep,
    audit,
    text="Please delete my account and all personal data you hold about me.",
):
    """A deletion_requests.csv row for a custom case."""
    return {
        "case_id": cid,
        "email": email,
        "requested_at": req,
        "reported_status": status,
        "reported_at": rep,
        "audit_at": audit,
        "request_text": text,
    }


def delete(aid, at, account, result):
    """A DELETE_RECORD system_activity.csv row for an account."""
    return {
        "activity_id": aid,
        "event_time": at,
        "event_type": "DELETE_RECORD",
        "source_system": "deletion_worker",
        "target_system": "account_service",
        "resource_id": account,
        "reported_result": result,
        "details": f"Deletion worker submitted primary profile {account} to account_service.",
    }


def step(phase, op, sys_, res, state, ev=""):
    """One expected step, written by hand (step_no is set by the runner)."""
    return {
        "phase": phase,
        "system_id": sys_,
        "resource_id": res,
        "operation": op,
        "state": state,
        "evidence_id": ev,
    }


SQL_COLS = (
    "resource_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT NOT "
    "NULL, "
    "phone TEXT NOT NULL, account_status TEXT NOT NULL, updated_at TEXT NOT NULL"
)


def sql(captured, primary=(), replica=()):
    """A SQLite snapshot with a primary and a replica customer_profiles table."""
    out = [
        "-- Ghost Data Still Exists: point-in-time database snapshot",
        "-- Dialect: SQLite-compatible SQL",
        f"-- Captured at: {captured}",
        "-- Database topology: failover_replica",
        "",
        "BEGIN TRANSACTION;",
    ]
    for table, rows in (
        ("customer_profiles_failover_replica", replica),
        ("customer_profiles_primary", primary),
    ):
        out.append(f"CREATE TABLE {table} ({SQL_COLS});")
        out += [f'INSERT INTO "{table}" VALUES({", ".join(repr(v) for v in r)});' for r in rows]
    return "\n".join(out + ["COMMIT;", ""])


def bundle(captured, tombstones):
    """A JSON snapshot bundle holding one deleted_customer_references collection."""
    import json

    return (
        json.dumps(
            {
                "exported_at": captured,
                "source": "records_assurance_service",
                "snapshots": [
                    {
                        "captured_at": captured,
                        "data_store": "account_service",
                        "collection": "customer_profiles",
                        "records": [],
                    },
                    {
                        "captured_at": captured,
                        "data_store": "identity_service",
                        "collection": "deleted_customer_references",
                        "records": tombstones,
                    },
                ],
            },
            indent=2,
        )
        + "\n"
    )


def tomb(rid, uid, name=None, email=None, phone=None):
    """One account tombstone record, with the direct identifiers that are still set."""
    return {
        "resource_id": rid,
        "subject_reference": uid,
        "name": name,
        "email": email,
        "phone": phone,
        "email_hash": _sha(email) if email else None,
        "account_status": "DELETED",
    }


V, F, R = "VERIFICATION", "FINDING", "REMEDIATION"

CASES = [
    {
        "id": "case_9001",
        "title": "replica-only account",
        "why": "The primary table no longer holds the account, but the failover replica still "
        "does: the account is PRESENT (docs/02 §5.2).",
        "people": [
            person("user_9001", "Ilona Varkas", "ilona.varkas@example.net", "+48 600 100 001")
        ],
        "requests": [
            request(
                "case_9001",
                "ilona.varkas@example.net",
                "2027-03-01T08:00:00Z",
                "COMPLETE",
                "2027-03-02T08:00:00Z",
                "2027-03-03T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90001", "2027-03-02T07:00:00Z", "account_90001", "SUCCESS")],
        "files": [
            (
                "custom_e9001",
                "evidence/custom/custom_e9001.sql",
                "2027-03-02T10:00:00Z",
                sql(
                    "2027-03-02T10:00:00Z",
                    replica=[
                        (
                            "account_90001",
                            "user_9001",
                            "Ilona Varkas",
                            "ilona.varkas@example.net",
                            "+48 600 100 001",
                            "ACTIVE",
                            "2027-03-02T09:55:00Z",
                        )
                    ],
                ),
            )
        ],
        "expect": {
            "case_9001": (
                "INCOMPLETE",
                [
                    step(
                        F,
                        "REPORT_REMAINING_RECORD",
                        "account_service",
                        "account_90001",
                        "PRESENT",
                        "custom_e9001",
                    ),
                    step(R, "DELETE_RECORD", "account_service", "account_90001", "ABSENT"),
                    step(V, "VERIFY_RECORD_ABSENT", "account_service", "account_90001", "ABSENT"),
                ],
            )
        },
    },
    {
        "id": "case_9002",
        "title": "DELETION_PENDING account",
        "why": "SUCCESS claim and reported COMPLETE, but the row still exists with the email (ADR "
        "0010).",
        "people": [
            person("user_9002", "Tomas Reyes", "tomas.reyes@example.net", "+34 600 100 002")
        ],
        "requests": [
            request(
                "case_9002",
                "tomas.reyes@example.net",
                "2027-03-04T08:00:00Z",
                "COMPLETE",
                "2027-03-05T08:00:00Z",
                "2027-03-06T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90002", "2027-03-05T07:10:00Z", "account_90002", "SUCCESS")],
        "files": [
            (
                "custom_e9002",
                "evidence/custom/custom_e9002.sql",
                "2027-03-06T07:00:00Z",
                sql(
                    "2027-03-06T07:00:00Z",
                    primary=[
                        (
                            "account_90002",
                            "user_9002",
                            "Tomas Reyes",
                            "tomas.reyes@example.net",
                            "+34 600 100 002",
                            "DELETION_PENDING",
                            "2027-03-06T06:30:00Z",
                        )
                    ],
                ),
            )
        ],
        "expect": {
            "case_9002": (
                "INCOMPLETE",
                [
                    step(
                        F,
                        "REPORT_REMAINING_RECORD",
                        "account_service",
                        "account_90002",
                        "PRESENT",
                        "custom_e9002",
                    ),
                    step(R, "DELETE_RECORD", "account_service", "account_90002", "ABSENT"),
                    step(V, "VERIFY_RECORD_ABSENT", "account_service", "account_90002", "ABSENT"),
                ],
            )
        },
    },
    {
        "id": "case_9003",
        "title": "contradicted catalog link",
        "why": "A LINK_RESOURCE_IDENTITY claim gives marketing_90003 to the subject, but the "
        "artifact captured 7 minutes earlier shows another person: rejected, no step (ADR "
        "0005). (Screens are hash-keyed transcriptions, so the artifact here is a log "
        "export.)",
        "people": [
            person("user_9003", "Mira Solberg", "mira.solberg@example.net", "+47 900 100 003")
        ],
        "requests": [
            request(
                "case_9003",
                "mira.solberg@example.net",
                "2027-03-07T08:00:00Z",
                "COMPLETE",
                "2027-03-08T08:00:00Z",
                "2027-03-09T08:00:00Z",
            )
        ],
        "activity": [
            delete("activity_90003", "2027-03-08T07:00:00Z", "account_90003", "SUCCESS"),
            {
                "activity_id": "activity_90013",
                "event_time": "2027-03-08T09:07:00Z",
                "event_type": "LINK_RESOURCE_IDENTITY",
                "source_system": "data_catalog",
                "target_system": "marketing_platform",
                "resource_id": "marketing_90003",
                "reported_result": "SUCCESS",
                "details": "Data catalog linked marketing_90003 (marketing_90003) to "
                "mira.solberg@example.net and user_9003.",
            },
        ],
        "files": [
            (
                "custom_e9003",
                "evidence/custom/custom_e9003.log",
                "2027-03-08T09:00:00Z",
                "\n".join(
                    lookup(
                        "2027-03-08T08:30:00Z",
                        "mira.solberg@example.net",
                        "account_90003",
                        trace="tr-c3a",
                    )
                    + [
                        L(
                            "2027-03-08T08:40:00Z",
                            "marketing_platform",
                            "tr-c3b",
                            "profile_read_started",
                            'lookup_key="noor.vale@example.org" attempt=1',
                        ),
                        L(
                            "2027-03-08T08:40:01Z",
                            "marketing_platform",
                            "tr-c3b",
                            "profile_read_completed",
                            "resource_id=marketing_90003 rows=1",
                        ),
                    ]
                )
                + "\n",
            )
        ],
        "expect": {
            "case_9003": (
                "COMPLETE",
                [
                    step(
                        V,
                        "VERIFY_RECORD_ABSENT",
                        "account_service",
                        "account_90003",
                        "ABSENT",
                        "custom_e9003",
                    )
                ],
            )
        },
        "log": {"case_9003": ["REJECTED_LINK(activity_90013 marketing_90003"]},
    },
    {
        "id": "case_9004",
        "title": "legal hold",
        "why": "A pre-audit legal_hold_N for the subject is retained and verified present, never "
        "deleted (ADR 0011).",
        "people": [
            person("user_9004", "Arne Lindqvist", "arne.lindqvist@example.net", "+46 700 100 004")
        ],
        "requests": [
            request(
                "case_9004",
                "arne.lindqvist@example.net",
                "2027-03-10T08:00:00Z",
                "COMPLETE",
                "2027-03-11T08:00:00Z",
                "2027-03-12T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90004", "2027-03-11T07:00:00Z", "account_90004", "SUCCESS")],
        "files": [
            (
                "custom_e9004",
                "evidence/custom/custom_e9004.log",
                "2027-03-11T10:00:00Z",
                "\n".join(
                    lookup(
                        "2027-03-11T09:00:00Z",
                        "arne.lindqvist@example.net",
                        "account_90004",
                        trace="tr-c4a",
                    )
                    + [
                        L(
                            "2027-03-11T09:10:00Z",
                            "legal_service",
                            "tr-c4b",
                            "retained_order_query_started",
                            'subject_ref="user_9004" attempt=1',
                        ),
                        L(
                            "2027-03-11T09:10:02Z",
                            "legal_service",
                            "tr-c4b",
                            "retained_order_loaded",
                            'resource_id=legal_hold_90004 reason="payment_dispute" '
                            'access="allowed"',
                        ),
                    ]
                )
                + "\n",
            )
        ],
        "expect": {
            "case_9004": (
                "COMPLETE",
                [
                    step(
                        V,
                        "VERIFY_RECORD_ABSENT",
                        "account_service",
                        "account_90004",
                        "ABSENT",
                        "custom_e9004",
                    ),
                    step(
                        V,
                        "VERIFY_RECORD_PRESENT",
                        "legal_service",
                        "legal_hold_90004",
                        "PRESENT",
                        "custom_e9004",
                    ),
                ],
            )
        },
    },
    {
        "id": "case_9005",
        "title": "uppercase historical email",
        "why": "The request uses the subject's OLD email in upper case; evidence uses the old "
        "email in lower case. Exact, case-insensitive matching over the audit chain.",
        "people": [
            person("user_9005", "Lena Okoro", "lena.okoro.new@example.net", "+234 800 100 005")
        ],
        "audit": [
            {
                "audit_id": "audit_90005",
                "user_id": "user_9005",
                "event_time": "2027-01-15T00:00:00Z",
                "field_name": "email",
                "old_value": "lena.okoro@example.net",
                "new_value": "lena.okoro.new@example.net",
            }
        ],
        "requests": [
            request(
                "case_9005",
                "LENA.OKORO@EXAMPLE.NET",
                "2027-03-13T08:00:00Z",
                "NOT_STARTED",
                "2027-03-14T08:00:00Z",
                "2027-03-15T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90005", "2027-03-14T07:00:00Z", "account_90005", "FAILED")],
        "files": [
            (
                "custom_e9005",
                "evidence/custom/custom_e9005.log",
                "2027-03-14T10:00:00Z",
                "\n".join(
                    lookup(
                        "2027-03-14T09:00:00Z",
                        "lena.okoro@example.net",
                        "account_90005",
                        trace="tr-c5a",
                    )
                    + search(
                        "2027-03-14T09:05:00Z",
                        "lena.okoro@example.net",
                        "search_90005",
                        trace="tr-c5b",
                    )
                )
                + "\n",
            )
        ],
        "expect": {
            "case_9005": (
                "INCOMPLETE",
                [
                    step(
                        F,
                        "REPORT_REMAINING_RECORD",
                        "search_service",
                        "search_90005",
                        "PRESENT",
                        "custom_e9005",
                    ),
                    step(R, "DELETE_RECORD", "search_service", "search_90005", "ABSENT"),
                    step(V, "VERIFY_RECORD_ABSENT", "account_service", "account_90005", "ABSENT"),
                    step(V, "VERIFY_RECORD_ABSENT", "search_service", "search_90005", "ABSENT"),
                ],
            )
        },
    },
    {
        "id": "case_9006",
        "title": "post-cutoff resurrection",
        "why": "A file captured AFTER audit_at shows the account active again; it must not change "
        "the answer (ADR 0002).",
        "people": [
            person("user_9006", "Pavel Novak", "pavel.novak@example.net", "+420 600 100 006")
        ],
        "requests": [
            request(
                "case_9006",
                "pavel.novak@example.net",
                "2027-03-16T08:00:00Z",
                "COMPLETE",
                "2027-03-17T08:00:00Z",
                "2027-03-18T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90006", "2027-03-17T07:00:00Z", "account_90006", "SUCCESS")],
        "files": [
            (
                "custom_e9006a",
                "evidence/custom/custom_e9006a.log",
                "2027-03-17T10:00:00Z",
                "\n".join(
                    lookup(
                        "2027-03-17T09:00:00Z",
                        "pavel.novak@example.net",
                        "account_90006",
                        trace="tr-c6a",
                    )
                )
                + "\n",
            ),
            (
                "custom_e9006b",
                "evidence/custom/custom_e9006b.log",
                "2027-03-19T10:00:00Z",
                "\n".join(
                    lookup(
                        "2027-03-19T09:00:00Z",
                        "pavel.novak@example.net",
                        "account_90006",
                        found=True,
                        trace="tr-c6b",
                    )
                )
                + "\n",
            ),
        ],
        "expect": {
            "case_9006": (
                "COMPLETE",
                [
                    step(
                        V,
                        "VERIFY_RECORD_ABSENT",
                        "account_service",
                        "account_90006",
                        "ABSENT",
                        "custom_e9006a",
                    )
                ],
            )
        },
    },
    {
        "id": "case_9007",
        "title": "redacted tombstone",
        "why": "The tombstone keeps only the stable user reference: compliant, "
        "VERIFY_RECORD_REDACTED (rule_15). The account is absent by omission from the "
        "covering snapshot (ADR 0014).",
        "people": [
            person("user_9007", "Ines Duarte", "ines.duarte@example.net", "+351 910 100 007")
        ],
        "requests": [
            request(
                "case_9007",
                "ines.duarte@example.net",
                "2027-03-19T08:00:00Z",
                "COMPLETE",
                "2027-03-20T08:00:00Z",
                "2027-03-21T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90007", "2027-03-20T07:00:00Z", "account_90007", "SUCCESS")],
        "files": [
            (
                "custom_e9007",
                "evidence/custom/custom_e9007.json",
                "2027-03-20T12:00:00Z",
                bundle("2027-03-20T12:00:00Z", [tomb("tombstone_90007", "user_9007")]),
            )
        ],
        "expect": {
            "case_9007": (
                "COMPLETE",
                [
                    step(
                        V,
                        "VERIFY_RECORD_ABSENT",
                        "account_service",
                        "account_90007",
                        "ABSENT",
                        "custom_e9007",
                    ),
                    step(
                        V,
                        "VERIFY_RECORD_REDACTED",
                        "identity_service",
                        "tombstone_90007",
                        "REDACTED",
                        "custom_e9007",
                    ),
                ],
            )
        },
    },
    {
        "id": "case_9008",
        "title": "exposed tombstone",
        "why": "The tombstone still holds name, email, phone and hash: REPORT_EXPOSED_PII + "
        "REDACT_RECORD, never deleted (rule_15).",
        "people": [
            person("user_9008", "Kwesi Boateng", "kwesi.boateng@example.net", "+233 20 100 0008")
        ],
        "requests": [
            request(
                "case_9008",
                "kwesi.boateng@example.net",
                "2027-03-22T08:00:00Z",
                "COMPLETE",
                "2027-03-23T08:00:00Z",
                "2027-03-24T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90008", "2027-03-23T07:00:00Z", "account_90008", "SUCCESS")],
        "files": [
            (
                "custom_e9008",
                "evidence/custom/custom_e9008.json",
                "2027-03-23T12:00:00Z",
                bundle(
                    "2027-03-23T12:00:00Z",
                    [
                        tomb(
                            "tombstone_90008",
                            "user_9008",
                            "Kwesi Boateng",
                            "kwesi.boateng@example.net",
                            "+233 20 100 0008",
                        )
                    ],
                ),
            )
        ],
        "expect": {
            "case_9008": (
                "INCOMPLETE",
                [
                    step(
                        F,
                        "REPORT_EXPOSED_PII",
                        "identity_service",
                        "tombstone_90008",
                        "PRESENT",
                        "custom_e9008",
                    ),
                    step(R, "REDACT_RECORD", "identity_service", "tombstone_90008", "REDACTED"),
                    step(V, "VERIFY_RECORD_ABSENT", "account_service", "account_90008", "ABSENT"),
                    step(
                        V,
                        "VERIFY_RECORD_REDACTED",
                        "identity_service",
                        "tombstone_90008",
                        "REDACTED",
                    ),
                ],
            )
        },
    },
    {
        "id": "case_9009",
        "title": "marketing-only trap (non-deletion)",
        "why": "The text says 'remove' but limits the request to marketing lists and forbids "
        "closing the account: NOT_APPLICABLE with [].",
        "people": [
            person("user_9009", "Yara Haddadin", "yara.haddadin@example.net", "+962 79 100 0009")
        ],
        "requests": [
            request(
                "case_9009",
                "yara.haddadin@example.net",
                "2027-03-25T08:00:00Z",
                "COMPLETE",
                "2027-03-26T08:00:00Z",
                "2027-03-27T08:00:00Z",
                "Please remove me from your marketing lists only. Do not close or delete my "
                "account; I still shop with you.",
            )
        ],
        "activity": [],
        "files": [],
        "expect": {"case_9009": ("NOT_APPLICABLE", [])},
    },
    {
        "id": "case_9010",
        "title": "tied account candidates (two requests)",
        "why": "Two requests share a reported_at; two SUCCESS account deletes fit both windows and "
        "no evidence separates them: no account step for either, UNRESOLVED_LINK logged "
        "(ADR 0004).",
        "people": [
            person("user_9010", "Jonas Aalto", "jonas.aalto@example.net", "+358 40 100 0010"),
            person("user_9011", "Maren Holt", "maren.holt@example.net", "+47 900 100 011"),
        ],
        "requests": [
            request(
                "case_9010",
                "jonas.aalto@example.net",
                "2027-03-28T08:00:00Z",
                "COMPLETE",
                "2027-03-29T08:00:00Z",
                "2027-03-30T08:00:00Z",
            ),
            request(
                "case_9011",
                "maren.holt@example.net",
                "2027-03-28T08:00:00Z",
                "COMPLETE",
                "2027-03-29T08:00:00Z",
                "2027-03-30T08:00:00Z",
            ),
        ],
        "activity": [
            delete("activity_90010", "2027-03-29T07:00:00Z", "account_90010", "SUCCESS"),
            delete("activity_90011", "2027-03-29T07:05:00Z", "account_90011", "SUCCESS"),
        ],
        "files": [
            (
                "custom_e9010",
                "evidence/custom/custom_e9010.log",
                "2027-03-29T10:00:00Z",
                "\n".join(
                    search(
                        "2027-03-29T09:00:00Z",
                        "jonas.aalto@example.net",
                        "search_90010",
                        trace="tr-c10a",
                    )
                    + search(
                        "2027-03-29T09:01:00Z",
                        "maren.holt@example.net",
                        "search_90011",
                        trace="tr-c10b",
                    )
                )
                + "\n",
            )
        ],
        "expect": {
            c: (
                "INCOMPLETE",
                [
                    step(
                        F, "REPORT_REMAINING_RECORD", "search_service", s, "PRESENT", "custom_e9010"
                    ),
                    step(R, "DELETE_RECORD", "search_service", s, "ABSENT"),
                    step(V, "VERIFY_RECORD_ABSENT", "search_service", s, "ABSENT"),
                ],
            )
            for c, s in (("case_9010", "search_90010"), ("case_9011", "search_90011"))
        },
        "log": {
            c: [
                "UNRESOLVED_LINK(primary account: 2 candidates survive",
                "account_90010/activity_90010",
                "account_90011/activity_90011",
            ]
            for c in ("case_9010", "case_9011")
        },
    },
    {
        "id": "case_9012",
        "title": "attempted-but-unproven account delete",
        "why": "The only account signal is a FAILED delete claim and no file shows the account: a "
        "future VERIFY_RECORD_ABSENT only, never a finding citing the claim (ADR 0006 "
        "amended).",
        "people": [
            person("user_9012", "Odile Marchand", "odile.marchand@example.net", "+33 6 10 00 00 12")
        ],
        "requests": [
            request(
                "case_9012",
                "odile.marchand@example.net",
                "2027-03-31T08:00:00Z",
                "NOT_STARTED",
                "2027-04-01T08:00:00Z",
                "2027-04-02T08:00:00Z",
            )
        ],
        "activity": [delete("activity_90012", "2027-04-01T07:00:00Z", "account_90012", "FAILED")],
        "files": [
            (
                "custom_e9012",
                "evidence/custom/custom_e9012.log",
                "2027-04-01T10:00:00Z",
                "\n".join(
                    search(
                        "2027-04-01T09:00:00Z",
                        "odile.marchand@example.net",
                        "search_90012",
                        trace="tr-c12",
                    )
                )
                + "\n",
            )
        ],
        "expect": {
            "case_9012": (
                "INCOMPLETE",
                [
                    step(
                        F,
                        "REPORT_REMAINING_RECORD",
                        "search_service",
                        "search_90012",
                        "PRESENT",
                        "custom_e9012",
                    ),
                    step(R, "DELETE_RECORD", "search_service", "search_90012", "ABSENT"),
                    step(V, "VERIFY_RECORD_ABSENT", "account_service", "account_90012", "ABSENT"),
                    step(V, "VERIFY_RECORD_ABSENT", "search_service", "search_90012", "ABSENT"),
                ],
            )
        },
    },
]

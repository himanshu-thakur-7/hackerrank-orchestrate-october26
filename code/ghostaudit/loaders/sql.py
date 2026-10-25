"""SQLite-compatible SQL snapshots, executed into an in-memory database (stdlib sqlite3).

Three layouts, recognised by table SHAPE (not file name):
  * typed tables (customer_profiles[_primary|_failover_replica], search_documents_primary, ...)
  * inventory snapshots: typed tables plus snapshot_scope(origin_system, captured_at)
  * generic tables with (resource_id, origin_system, collection_name, record_json, updated_at)

Coverage (absence by omission) and why it is sound here:
  * A SQL dump is CREATE TABLE plus every INSERT of that table at one point in time, so a resource
    of the table's system that is not listed was not in that table. Gold relies on this
    (VERIFY_RECORD_ABSENT cites a failover/primary dump that simply lacks the account).
  * Inventory snapshots declare their scope explicitly: coverage only for systems in snapshot_scope.
  * Generic tables hold several systems: coverage per (origin_system, table) for systems the dump
    lists.
"""

import json
import re
import sqlite3

from ghostaudit.loaders.common import (
    ISO_RE,
    LoadResult,
    Unit,
    attrs,
    emails_in_text,
    identifiers,
    pii_fields,
    scalar_items,
    state_from_fields,
)
from ghostaudit.store import Coverage, Observation

TYPED = [  # table base name -> (system_id, category from the table's declared content)
    ("customer_profiles", "account_service", "USER_PROFILE"),
    ("customer_search_documents", "search_service", "SEARCH_INDEX_ENTRY"),
    ("search_documents", "search_service", "SEARCH_INDEX_ENTRY"),
    ("customer_analytics_profiles", "analytics_platform", "ANALYTICS_PROFILE"),
    ("support_records", "support_platform", None),
    ("customer_exports", "export_service", "USER_EXPORT"),
    ("connector_subscriptions", "integration_service", None),
    ("backup_restore_entries", "backup_service", "BACKUP_ARCHIVE"),
    ("security_audit_records", "security_service", "SECURITY_AUDIT_LOG"),
]
COLLECTION_CATEGORY = {
    "customer_profiles": "USER_PROFILE",
    "customer_search_documents": "SEARCH_INDEX_ENTRY",
    "customer_analytics_reports": "ANALYTICS_PROFILE",
    "support_conversations": "SUPPORT_MESSAGE",
    "ticket_attachments": "SUPPORT_ATTACHMENT",
    "customer_export_jobs": "USER_EXPORT",
    "backup_catalog": "BACKUP_ARCHIVE",
    "security_audit_events": "SECURITY_AUDIT_LOG",
    "retained_order_records": "LEGAL_HOLD_RECORD",
    "deleted_customer_references": "ACCOUNT_TOMBSTONE",
    "connector_configurations": None,
}
GENERIC_COLS = {"resource_id", "origin_system", "collection_name", "record_json"}
TIME_COLS = ("updated_at", "indexed_at")
INSERT_RE = re.compile(r"^INSERT INTO\s+\"?(\w+)\"?\s+VALUES\s*\(\s*'([^']*)'")


def matches(text):
    return "CREATE TABLE" in text and "INSERT INTO" in text


def _typed(table):
    for base, system, cat in TYPED:
        if table == base or table.startswith(base + "_"):
            return system, cat
    return None


def load(file_id, captured_at, text):
    db = sqlite3.connect(":memory:")
    try:
        db.executescript(text)
        return _load(file_id, captured_at, text, db)
    finally:
        db.close()


def _load(file_id, captured_at, text, db):
    r = LoadResult("sql")
    lines = {}
    for n, line in enumerate(text.splitlines(), 1):
        m = INSERT_RE.match(line)
        if m:
            lines.setdefault((m.group(1), m.group(2)), n)
    tables = [
        t for (t,) in db.execute("select name from sqlite_master where type='table' order by name")
    ]
    scope = {}
    if "snapshot_scope" in tables:
        scope = dict(db.execute("select origin_system, captured_at from snapshot_scope"))
    for table in tables:
        if table == "snapshot_scope":
            continue
        cols = [c[1] for c in db.execute(f'pragma table_info("{table}")')]
        rows = [dict(zip(cols, row, strict=True)) for row in db.execute(f'select * from "{table}"')]
        typed = _typed(table)
        generic = set(cols) >= GENERIC_COLS
        if not typed and not generic:
            r.unparsed.append(
                Unit(
                    file_id,
                    f"table {table}",
                    f"columns {cols}",
                    f"unknown table '{table}' ({len(rows)} row{'s' if len(rows) != 1 else ''})",
                )
            )
            continue
        systems_listed = set()
        for row in rows:
            if generic:
                system, coll = row["origin_system"], row["collection_name"]
                cat = COLLECTION_CATEGORY.get(coll)
                blob = json.loads(row["record_json"])
                fields = {k: v for k, v in blob.items() if not isinstance(v, (dict, list))}
                if isinstance(blob.get("document"), dict):
                    fields.update(blob["document"])
                fields["collection"] = coll
                observed = row.get("updated_at") or captured_at
            else:
                system, cat = typed
                fields = dict(row)
                observed = next(
                    (
                        row[c]
                        for c in TIME_COLS
                        if isinstance(row.get(c), str) and ISO_RE.match(row[c])
                    ),
                    captured_at,
                )
            systems_listed.add(system)
            loc = f"line {lines.get((table, row['resource_id']), '?')}"
            free = emails_in_text(fields)
            pii = pii_fields(fields)
            if free and "email" not in pii:
                pii = tuple(
                    p for p in ("name", "email", "phone", "email_hash") if p in pii or p == "email"
                )
            o = Observation(
                file_id,
                observed,
                system,
                row["resource_id"],
                table,
                state_from_fields(fields),
                category=cat,
                pii_fields=pii,
                identifiers=identifiers(*(v for _, v in scalar_items(fields)), *free),
                locator=loc,
                attrs=attrs(fields, exclude=TIME_COLS + ("collection",)),
            )
            r.observations.append(o)
            if not o.identifiers:
                r.unattributed.append(
                    Unit(file_id, loc, json.dumps(fields, default=str)[:200], "no identifier")
                )
        if scope:
            if typed and typed[0] in scope:
                r.coverage.append(Coverage(file_id, scope[typed[0]], typed[0], table))
        elif typed:
            r.coverage.append(Coverage(file_id, captured_at, typed[0], table))
        else:
            r.coverage += [Coverage(file_id, captured_at, s, table) for s in sorted(systems_listed)]
    return r

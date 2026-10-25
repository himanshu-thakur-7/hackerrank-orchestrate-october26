"""One data record (a row of a collection) -> Observation. Shared by bundle and collection-list loaders."""

import json

from ghostaudit.loaders.common import (
    Unit,
    attrs,
    emails_in_text,
    identifiers,
    pii_fields,
    scalar_items,
    state_from_fields,
)
from ghostaudit.store import Observation

COLLECTION_SYSTEM = {
    "customer_profiles": "account_service",
    "customer_search_documents": "search_service",
    "customer_analytics_reports": "analytics_platform",
    "support_conversations": "support_platform",
    "ticket_attachments": "support_platform",
    "customer_export_jobs": "export_service",
    "backup_catalog": "backup_service",
    "security_audit_events": "security_service",
    "retained_order_records": "legal_service",
    "deleted_customer_references": "identity_service",
    "connector_configurations": "integration_service",
}


def observation(file_id, rec, system, collection, category, observed_at, locator, result_out):
    fields = {k: v for k, v in rec.items() if not isinstance(v, (dict, list))}
    if isinstance(rec.get("document"), dict):
        fields.update(rec["document"])
    free = emails_in_text(fields)
    pii = pii_fields(fields)
    if free and "email" not in pii:
        pii = tuple(p for p in ("name", "email", "phone", "email_hash") if p in pii or p == "email")
    o = Observation(
        file_id,
        observed_at,
        system,
        rec["resource_id"],
        collection,
        state_from_fields(fields),
        category=category,
        pii_fields=pii,
        identifiers=identifiers(*(v for _, v in scalar_items(fields)), *free),
        locator=locator,
        attrs=attrs(fields),
    )
    result_out.observations.append(o)
    if not o.identifiers:
        result_out.unattributed.append(
            Unit(file_id, locator, json.dumps(rec, default=str)[:200], "no identifier")
        )
    return o

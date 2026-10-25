"""One data record (a row of a collection) -> Observation. Shared by bundle and collection-list
loaders."""

from __future__ import annotations

import json

from ghostaudit.loaders.common import (
    Unit,
    attrs,
    exposed_with_free_emails,
    identifiers,
    scalar_items,
    state_from_fields,
)
from ghostaudit.store import Observation

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ghostaudit.loaders.common import LoadResult
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


def observation(
    file_id: str,
    rec: Mapping[str, Any],
    system: str,
    collection: str,
    category: str | None,
    observed_at: str,
    locator: str,
    result_out: LoadResult,
) -> Observation:
    fields = {k: v for k, v in rec.items() if not isinstance(v, (dict, list))}
    if isinstance(rec.get("document"), dict):
        fields.update(rec["document"])
    pii, free = exposed_with_free_emails(fields)
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

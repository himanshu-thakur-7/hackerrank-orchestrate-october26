"""Output contract (AGENTS.md §6.4): the 15 (phase, operation, state) triples, in sort order.
The position of an operation in this list is its op_rank, the first part of the step sort key."""

TRIPLES = (
    ("FINDING", "REPORT_REMAINING_RECORD", "PRESENT"),
    ("FINDING", "REPORT_EXPOSED_PII", "PRESENT"),
    ("FINDING", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
    ("FINDING", "REPORT_RESTORE_RISK", "ACTIVE"),
    ("REMEDIATION", "DISABLE_DATA_FLOW", "DISABLED"),
    ("REMEDIATION", "BLOCK_RESTORE", "BLOCKED"),
    ("REMEDIATION", "DELETE_RECORD", "ABSENT"),
    ("REMEDIATION", "REDACT_RECORD", "REDACTED"),
    ("REMEDIATION", "ANONYMIZE_RECORD", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_RECORD_ABSENT", "ABSENT"),
    ("VERIFICATION", "VERIFY_RECORD_PRESENT", "PRESENT"),
    ("VERIFICATION", "VERIFY_RECORD_REDACTED", "REDACTED"),
    ("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
    ("VERIFICATION", "VERIFY_RESTORE_BLOCKED", "BLOCKED"),
)
OP_RANK = {op: i for i, (_, op, _) in enumerate(TRIPLES)}
PHASE = {op: phase for phase, op, _ in TRIPLES}
STATE = {op: state for _, op, state in TRIPLES}


def step(operation, system_id, resource_id, evidence_id=""):
    return {
        "step_no": 0,
        "phase": PHASE[operation],
        "system_id": system_id,
        "resource_id": resource_id,
        "operation": operation,
        "state": STATE[operation],
        "evidence_id": evidence_id,
    }


def ordered(steps):
    """Sort by (op_rank, system_id, resource_id) as plain strings, then number 1..n."""
    out = sorted(steps, key=lambda s: (OP_RANK[s["operation"]], s["system_id"], s["resource_id"]))
    for i, s in enumerate(out, 1):
        s["step_no"] = i
    return out

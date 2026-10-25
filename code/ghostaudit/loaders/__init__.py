"""Loaders: dispatch evidence files by CONTENT signature (never by file name) to one adapter each.

load_bytes(file_id, captured_at, raw) -> LoadResult; unknown content raises UnknownSignature.
Signatures whose adapter is not built yet raise LoaderPending (strict) so nothing is skipped silently.
"""
import json
from pathlib import Path

from ghostaudit.loaders import handover, readback, service_export
from ghostaudit.loaders.common import LoadResult, Unit  # noqa: F401  (re-exported)

PENDING = {}            # signature -> board task that will implement it


class UnknownSignature(Exception):
    pass


class LoaderPending(Exception):
    pass


LOADERS = {
    "txt:handover": handover.load,
    "json:service_exports": service_export.load,
    "log:readback": readback.load,
}
PENDING.update({"sql": "T05", "json:snapshots": "T06", "json:records": "T06", "log:record_lookup": "T06",
                "log:observability": "T07", "pdf": "T12", "png": "T12"})


def sniff(raw, file_id="?"):
    if raw.startswith(b"%PDF"):
        return "pdf"
    if raw.startswith(b"\x89PNG"):
        return "png"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise UnknownSignature(f"{file_id}: not UTF-8 text and not a known binary format (byte {e.start}); first bytes {raw[:16]!r}")
    head = text.lstrip()
    if head.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise UnknownSignature(f"{file_id}: starts like JSON but does not parse ({e.msg} at line {e.lineno})")
        keys = sorted(data) if isinstance(data, dict) else []
        if "service_exports" in keys:
            return "json:service_exports"
        if "snapshots" in keys:
            return "json:snapshots"
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return "json:records"
        raise UnknownSignature(f"{file_id}: unknown content signature: JSON object with keys {keys}")
    if "CREATE TABLE" in text and "INSERT INTO" in text:
        return "sql"
    if handover.matches(text):
        return "txt:handover"
    if readback.matches(text):
        return "log:readback"
    if "event=record_lookup" in text:
        return "log:record_lookup"
    first = next((l for l in text.splitlines() if l.strip()), "")
    if first[:20].count("-") >= 2 and "T" in first[:20] and first[19:20] == "Z":
        return "log:observability"
    raise UnknownSignature(f"{file_id}: unknown content signature; first line {first[:80]!r}")


def load_bytes(file_id, captured_at, raw, strict=True):
    sig = sniff(raw, file_id)
    if sig not in LOADERS:
        if strict:
            raise LoaderPending(f"{file_id}: signature {sig} has no loader yet ({PENDING.get(sig, 'unplanned')})")
        return LoadResult(sig)
    return LOADERS[sig](file_id, captured_at, raw.decode("utf-8"))


def load_manifest(data_dir, strict=True, only=None):
    """Load every evidence file listed in evidence_files.csv -> {file_id: LoadResult}."""
    import csv
    d = Path(data_dir)
    out = {}
    with open(d / "evidence_files.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if only and row["file_id"] not in only:
                continue
            raw = (d / row["file_path"]).read_bytes()
            out[row["file_id"]] = load_bytes(row["file_id"], row["captured_at"], raw, strict=strict)
    return out

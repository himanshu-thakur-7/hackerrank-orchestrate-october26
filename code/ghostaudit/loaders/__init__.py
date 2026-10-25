"""Loaders: dispatch evidence files by CONTENT signature (never by file name) to one adapter each.

load_bytes(file_id, captured_at, raw) -> LoadResult; unknown content raises UnknownSignature.
Signatures whose adapter is not built yet raise LoaderPending (strict) so nothing is skipped
silently.

Decisions: ADR 0007 (one-file-per-case structure is never a feature), ADR 0014
(which formats emit Coverage).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Container
from pathlib import Path

from ghostaudit.loaders import (
    bundle,
    handover,
    observability,
    pdf,
    readback,
    record_lookup,
    records,
    screens,
    service_export,
    sql,
)
from ghostaudit.loaders.common import LoadResult, Unit  # noqa: F401  (re-exported)

PENDING: dict[str, str] = {}  # signature -> board task that will implement it


class UnknownSignature(Exception):
    """Raised for a file whose content matches no known signature."""


class LoaderPending(Exception):
    """Raised (strict mode) for a known signature whose adapter is not built."""


LOADERS: dict[str, Callable[..., LoadResult]] = {
    "txt:handover": handover.load,
    "json:service_exports": service_export.load,
    "log:readback": readback.load,
    "sql": sql.load,
    "json:snapshots": bundle.load,
    "json:records": records.load,
    "log:record_lookup": record_lookup.load,
    "log:observability": observability.load,
    "pdf": pdf.load,
    "png": screens.load,
}
BINARY = {"pdf", "png"}  # these adapters take the raw bytes


# Content signatures, checked in this order (the first match wins).
BINARY_SIGNATURES = ((b"%PDF", "pdf"), (b"\x89PNG", "png"))
JSON_SIGNATURES = (
    ("json:service_exports", lambda data: "service_exports" in data),
    ("json:snapshots", lambda data: "snapshots" in data),
    ("json:records", lambda data: isinstance(data.get("records"), list)),
)
TEXT_SIGNATURES = (
    ("sql", sql.matches),
    ("txt:handover", handover.matches),
    ("log:readback", readback.matches),
    ("log:record_lookup", record_lookup.matches),
    ("log:observability", observability.matches),
)


def _decode(raw: bytes, file_id: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise UnknownSignature(
            f"{file_id}: not UTF-8 text and not a known binary format (byte {e.start}); first "
            f"bytes {raw[:16]!r}"
        ) from e


def _json_signature(text: str, file_id: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise UnknownSignature(
            f"{file_id}: starts like JSON but does not parse ({e.msg} at line {e.lineno})"
        ) from e
    if isinstance(data, dict):
        for sig, shape in JSON_SIGNATURES:
            if shape(data):
                return sig
    keys = sorted(data) if isinstance(data, dict) else []
    raise UnknownSignature(f"{file_id}: unknown content signature: JSON object with keys {keys}")


def sniff(raw: bytes, file_id: str = "?") -> str:
    """The content signature of one evidence file; UnknownSignature when nothing matches."""
    for magic, sig in BINARY_SIGNATURES:
        if raw.startswith(magic):
            return sig
    text = _decode(raw, file_id)
    if text.lstrip().startswith("{"):
        return _json_signature(text, file_id)
    for sig, matches in TEXT_SIGNATURES:
        if matches(text):
            return sig
    first = next((line for line in text.splitlines() if line.strip()), "")
    raise UnknownSignature(f"{file_id}: unknown content signature; first line {first[:80]!r}")


def load_bytes(file_id: str, captured_at: str, raw: bytes, strict: bool = True) -> LoadResult:
    """Load one evidence file by content signature.

    Binary adapters (pdf, png) get the bytes, text adapters the decoded text. Raises
    UnknownSignature for unknown content and, with strict=True, LoaderPending for a signature
    without an adapter; with strict=False that file yields an empty LoadResult."""
    sig = sniff(raw, file_id)
    if sig not in LOADERS:
        if strict:
            raise LoaderPending(
                f"{file_id}: signature {sig} has no loader yet ({PENDING.get(sig, 'unplanned')})"
            )
        return LoadResult(sig)
    if sig in BINARY:
        try:
            return LOADERS[sig](file_id, captured_at, raw)
        except screens.MissingTranscription as e:
            raise UnknownSignature(str(e)) from e
    return LOADERS[sig](file_id, captured_at, raw.decode("utf-8"))


def load_manifest(
    data_dir: str | Path, strict: bool = True, only: Container[str] | None = None
) -> dict[str, LoadResult]:
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

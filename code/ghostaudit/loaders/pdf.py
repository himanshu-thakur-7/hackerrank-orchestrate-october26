"""PDF business documents (signature: bytes start with %PDF). Text comes from `pdftotext -layout`,
with pypdf as a fallback. The dataset's own PDFs are also in the committed text cache
(pdf_text_cache.py, keyed by sha256, generated with pdftotext), so the default run needs no PDF
tool; a PDF that is neither cached nor extractable stops the run with PdfTextUnavailable (never
skipped).

A document with at most one resource id is one record unit: every exact identifier in it belongs to
that resource. With several resource ids, each line is its own unit. Lines that name a person but no
resource id (a register row, a statement) are kept as `unattributed` units. Documents describe a
record that exists, so state is PRESENT; observed_at is the file's captured_at (ADR 0002).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import cast

from ghostaudit.errors import GhostAuditError
from ghostaudit.loaders.common import (
    EMAIL_IN_TEXT,
    PREFIX_SYSTEM,
    LoadResult,
    Unit,
    identifiers,
    kind,
)
from ghostaudit.store import Observation

RES_RE = re.compile(r"\b(" + "|".join(sorted(PREFIX_SYSTEM, key=len, reverse=True)) + r")_\d+\b")
USER_RE = re.compile(r"\buser_\d+\b")
PHONE_RE = re.compile(r"\+\d[\d \-]{7,}\d")
NAME_RE = re.compile(
    r"^\s*Detail\s{2,}([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*$"
)  # a Detail row that is only a person's name
ATTR_RES = (
    ("file", re.compile(r"\bfile\s+(\S+\.\w{2,4})\b")),
    ("uploader", re.compile(r"\buploader\s+(\w+)")),
    ("ticket", re.compile(r"\b(?:ticket|reference)\s+(CS-\d+)")),
    ("retain_until", re.compile(r"\bretain until\s+(.+?)\s*$")),
    ("event", re.compile(r"^\s*Detail\s+event\s+(.+?)\s*$")),
)


class PdfTextUnavailable(GhostAuditError):
    """Raised for a PDF that is not in the text cache and that no backend can read."""


def _pdftotext(raw: bytes) -> str | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "doc.pdf"
        p.write_bytes(raw)
        out = subprocess.run([exe, "-layout", str(p), "-"], capture_output=True, check=True)
    return out.stdout.decode("utf-8", errors="replace")


def _pypdf(raw: bytes) -> str | None:
    try:
        import io

        import pypdf
    except ImportError:
        return None
    return "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(io.BytesIO(raw)).pages)


def extract_text(
    raw: bytes, backends: Sequence[Callable[[bytes], str | None]] = (_pdftotext, _pypdf)
) -> str:
    """The text of a PDF: the committed cache first, then each backend in order.

    Raises PdfTextUnavailable when nothing yields text, so a document is never skipped."""
    import hashlib

    from ghostaudit.loaders import pdf_text_cache

    cached = pdf_text_cache.TEXT.get(hashlib.sha256(raw).hexdigest())
    if cached is not None:
        return cached
    for b in backends:
        text = b(raw)
        if text is not None:
            return text
    raise PdfTextUnavailable(
        "no PDF text backend: install poppler-utils (pdftotext) or `pip install pypdf`"
    )


def _tokens(text: str) -> list[str]:
    out = EMAIL_IN_TEXT.findall(text) + USER_RE.findall(text) + PHONE_RE.findall(text)
    return [t.rstrip(".") for t in out]


def units(text: str) -> list[tuple[str, str, list[str]]]:
    """(locator, unit_text, resource_ids) record units of one document."""
    lines = text.splitlines()
    ids = sorted(set(m.group(0) for m in RES_RE.finditer(text)), key=lambda r: text.index(r))
    if len(ids) <= 1:
        first = next(
            (n for n, text_line in enumerate(lines, 1) if ids and ids[0] in text_line), None
        )
        return [(f"text line {first}" if first else "document", text, ids)]
    return [
        (f"text line {n}", text_line, [m.group(0) for m in RES_RE.finditer(text_line)])
        for n, text_line in enumerate(lines, 1)
        if text_line.strip()
    ]


def _without_resource_id(file_id: str, loc: str, unit: str, toks: Sequence[str]) -> list[Unit]:
    """Units for a text with no resource id. A register (several person rows, each with its own
    user id) yields one Unit per row; any other text with identifiers yields one Unit."""
    person_lines = [(n, line) for n, line in enumerate(unit.splitlines(), 1) if _tokens(line)]
    users = [tuple(USER_RE.findall(line)) for _, line in person_lines]
    if len(person_lines) > 1 and all(users) and len(set(users)) == len(users):
        return [
            Unit(file_id, f"text line {n}", line.strip(), "no resource id")
            for n, line in person_lines
        ]
    if toks:
        return [Unit(file_id, loc, " ".join(toks), "no resource id")]
    return []


def _exposed(toks: Sequence[str], unit: str) -> tuple[str, ...]:
    """Direct identifiers visible in the unit: emails and phones among its tokens, and a name."""
    pii = {k for k in map(kind, toks) if k in ("email", "phone")}
    if any(NAME_RE.match(line) for line in unit.splitlines()):
        pii.add("name")
    return tuple(p for p in ("name", "email", "phone") if p in pii)


def _attributes(unit: str) -> tuple[tuple[str, str], ...]:
    """The first value of each ATTR_RES attribute found in the unit, whitespace-normalized."""
    found = {}
    for line in unit.splitlines():
        for key, rx in ATTR_RES:
            m = rx.search(line)
            if m and key not in found:
                found[key] = re.sub(r"\s+", " ", m.group(1).strip())
    return tuple(sorted(found.items()))


def load(file_id: str, captured_at: str, raw: bytes) -> LoadResult:
    """Parse one evidence file of this format into a LoadResult.

    Inputs: the manifest file_id and captured_at, and the raw bytes. Output: Observations
    (and Coverage where the format is exhaustive); record-like units that cannot be used go to
    `unattributed` or `unparsed`, so nothing is dropped silently."""
    r = LoadResult("pdf")
    for loc, unit, ids in units(extract_text(raw)):
        toks = identifiers(*_tokens(unit))
        if not ids:
            r.unattributed += _without_resource_id(file_id, loc, unit, toks)
            continue
        pii, attrs = _exposed(toks, unit), _attributes(unit)
        for rid in ids:
            system = PREFIX_SYSTEM[cast("re.Match[str]", RES_RE.match(rid)).group(1)]
            r.observations.append(
                Observation(
                    file_id,
                    captured_at,
                    system,
                    rid,
                    "document",
                    "PRESENT",
                    pii_fields=pii,
                    identifiers=toks,
                    locator=loc,
                    attrs=attrs,
                )
            )
            if not toks:
                r.unattributed.append(Unit(file_id, loc, rid, "no identifier"))
    return r


def write_text_cache(pdf_paths: Iterable[str | Path], out_path: str | Path) -> None:
    """Regenerate pdf_text_cache.py from PDF files with pdftotext (run once per dataset version)."""
    import hashlib

    entries = {}
    for p in sorted(pdf_paths):
        raw = Path(p).read_bytes()
        entries[hashlib.sha256(raw).hexdigest()] = (Path(p).name, _pdftotext(raw))
    lines = [
        '"""GENERATED by ghostaudit.loaders.pdf.write_text_cache: `pdftotext -layout` text of the '
        "dataset PDFs,",
        "keyed by the sha256 of the PDF bytes, so the default run needs no PDF tool. Do not edit "
        'by hand."""',
        "",
        "TEXT = {",
    ]
    for k, (name, text) in sorted(entries.items()):
        lines.append(f"    # {name}")
        lines.append(f"    {k!r}: {text!r},")
    lines += ["}", ""]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")

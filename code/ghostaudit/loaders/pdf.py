"""PDF business documents (signature: bytes start with %PDF). Text comes from `pdftotext -layout`, with
pypdf as a fallback. The dataset's own PDFs are also in the committed text cache (pdf_text_cache.py,
keyed by sha256, generated with pdftotext), so the default run needs no PDF tool; a PDF that is neither
cached nor extractable stops the run with PdfTextUnavailable (never skipped).

A document with at most one resource id is one record unit: every exact identifier in it belongs to
that resource. With several resource ids, each line is its own unit. Lines that name a person but no
resource id (a register row, a statement) are kept as `unattributed` units. Documents describe a
record that exists, so state is PRESENT; observed_at is the file's captured_at (ADR 0002).
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

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


class PdfTextUnavailable(Exception):
    pass


def _pdftotext(raw):
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "doc.pdf"
        p.write_bytes(raw)
        out = subprocess.run([exe, "-layout", str(p), "-"], capture_output=True, check=True)
    return out.stdout.decode("utf-8", errors="replace")


def _pypdf(raw):
    try:
        import io
        import pypdf
    except ImportError:
        return None
    return "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(io.BytesIO(raw)).pages)


def extract_text(raw, backends=(_pdftotext, _pypdf)):
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


def _tokens(text):
    out = EMAIL_IN_TEXT.findall(text) + USER_RE.findall(text) + PHONE_RE.findall(text)
    return [t.rstrip(".") for t in out]


def units(text):
    """(locator, unit_text, resource_ids) record units of one document."""
    lines = text.splitlines()
    ids = sorted(set(m.group(0) for m in RES_RE.finditer(text)), key=lambda r: text.index(r))
    if len(ids) <= 1:
        first = next((n for n, l in enumerate(lines, 1) if ids and ids[0] in l), None)
        return [(f"text line {first}" if first else "document", text, ids)]
    return [
        (f"text line {n}", l, [m.group(0) for m in RES_RE.finditer(l)])
        for n, l in enumerate(lines, 1)
        if l.strip()
    ]


def load(file_id, captured_at, raw):
    r = LoadResult("pdf")
    text = extract_text(raw)
    for loc, unit, ids in units(text):
        toks = identifiers(*_tokens(unit))
        if not ids:
            person_lines = [(n, l) for n, l in enumerate(unit.splitlines(), 1) if _tokens(l)]
            users = [tuple(USER_RE.findall(l)) for _, l in person_lines]
            if len(person_lines) > 1 and all(users) and len(set(users)) == len(users):
                for n, l in person_lines:  # a register: one person per row
                    r.unattributed.append(
                        Unit(file_id, f"text line {n}", l.strip(), "no resource id")
                    )
            elif toks:
                r.unattributed.append(Unit(file_id, loc, " ".join(toks), "no resource id"))
            continue
        pii = set()
        for t in toks:
            k = kind(t)
            if k in ("email", "phone"):
                pii.add(k)
        if any(NAME_RE.match(l) for l in unit.splitlines()):
            pii.add("name")
        attrs = {}
        for line in unit.splitlines():
            for key, rx in ATTR_RES:
                m = rx.search(line)
                if m and key not in attrs:
                    attrs[key] = re.sub(r"\s+", " ", m.group(1).strip())
        for rid in ids:
            prefix = RES_RE.match(rid).group(1)
            o = Observation(
                file_id,
                captured_at,
                PREFIX_SYSTEM[prefix],
                rid,
                "document",
                "PRESENT",
                pii_fields=tuple(p for p in ("name", "email", "phone") if p in pii),
                identifiers=toks,
                locator=loc,
                attrs=tuple(sorted(attrs.items())),
            )
            r.observations.append(o)
            if not toks:
                r.unattributed.append(Unit(file_id, loc, rid, "no identifier"))
    return r


def write_text_cache(pdf_paths, out_path):
    """Regenerate pdf_text_cache.py from PDF files with pdftotext (run once per dataset version)."""
    import hashlib

    entries = {}
    for p in sorted(pdf_paths):
        raw = Path(p).read_bytes()
        entries[hashlib.sha256(raw).hexdigest()] = (Path(p).name, _pdftotext(raw))
    lines = [
        '"""GENERATED by ghostaudit.loaders.pdf.write_text_cache: `pdftotext -layout` text of the dataset PDFs,',
        'keyed by the sha256 of the PDF bytes, so the default run needs no PDF tool. Do not edit by hand."""',
        "",
        "TEXT = {",
    ]
    for k, (name, text) in sorted(entries.items()):
        lines.append(f"    # {name}")
        lines.append(f"    {k!r}: {text!r},")
    lines += ["}", ""]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")

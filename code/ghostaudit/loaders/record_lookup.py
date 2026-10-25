"""Record-lookup logs, one register row per line:

  '<ts> INFO service=<logger> event=record_lookup seq=N system="..." resource_id="..."
   record_type="..." result="..." subject_reference="..."'

Register semantics (see register.py): a history of checks, so no Coverage.

Decisions: ADR 0014 (no Coverage: the format is not exhaustive), ADR 0002 (observed_at)."""

from __future__ import annotations

import re

from ghostaudit.loaders import register
from ghostaudit.loaders.common import LoadResult, Unit, logfmt

LINE_RE = re.compile(
    r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) \w+ (service=\S+ event=record_lookup .*)$"
)


def matches(text: str) -> bool:
    """True when `text` has this format's content signature (never decided by file name)."""
    lines = [text_line for text_line in text.splitlines() if text_line.strip()]
    return bool(lines) and all(LINE_RE.match(text_line) for text_line in lines)


def load(file_id: str, captured_at: str, text: str) -> LoadResult:
    """Parse one evidence file of this format into a LoadResult.

    Inputs: the manifest file_id and captured_at, and the decoded text. Output: Observations
    (and Coverage where the format is exhaustive); record-like units that cannot be used go to
    `unattributed` or `unparsed`, so nothing is dropped silently."""
    r = LoadResult("log:record_lookup")
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        f = logfmt(m.group(2)) if m else {}
        if not m or not set(f) >= register.REGISTER_KEYS:
            r.unparsed.append(Unit(file_id, f"line {n}", line, "not a record_lookup line"))
            continue
        f["recorded_at"] = m.group(1)
        register.observation(
            file_id, f, f"{f['service']}.record_lookup", f"line {n}", m.group(1), r
        )
    return r

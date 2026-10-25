"""Record-lookup logs: '<ts> INFO service=<logger> event=record_lookup seq=N system="..."
resource_id="..."
record_type="..." result="..." subject_reference="..."'. Register semantics, no Coverage."""

import re

from ghostaudit.loaders import register
from ghostaudit.loaders.common import LoadResult, Unit, logfmt

LINE_RE = re.compile(
    r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) \w+ (service=\S+ event=record_lookup .*)$"
)


def matches(text):
    lines = [text_line for text_line in text.splitlines() if text_line.strip()]
    return bool(lines) and all(LINE_RE.match(text_line) for text_line in lines)


def load(file_id, captured_at, text):
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

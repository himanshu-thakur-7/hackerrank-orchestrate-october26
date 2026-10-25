"""Literal audit: solver and evaluation code must not name specific cases or evidence files.

scan(root) -> ["relative/path:line: literal", ...]; empty means clean.
Files under any tests/ or fixtures/ directory are exempt (fixtures hold labeled data by design), and
so are the generated reports in GENERATED_REPORTS: they document results case by case and no code
reads them.
"""

import re
from pathlib import Path

PATTERN = re.compile(r"\b(?:case|evidence)_\d+\b")
EXEMPT_DIRS = {"tests", "fixtures", "__pycache__"}
GENERATED_REPORTS = {
    "evaluation_report.md",
    "usage_report.md",
    "intent_disagreements.md",
    "holdout_reveals.md",
}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml"}


def scan(root):
    root = Path(root)
    hits = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if (
            not p.is_file()
            or p.suffix not in TEXT_SUFFIXES
            or EXEMPT_DIRS & set(rel.parts[:-1])
            or p.name in GENERATED_REPORTS
        ):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in PATTERN.finditer(line):
                hits.append(f"{rel.as_posix()}:{i}: {m.group(0)}")
    return hits

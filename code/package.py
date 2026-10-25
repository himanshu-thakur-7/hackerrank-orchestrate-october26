"""Build code.zip for submission: README.md and code/, plus evaluation/ holding copies of the two
generated reports and docs/ holding SANITIZED copies of the design documents (ADRs, design, ledgers,
audits, board).

docs/ copies are made at build time and the originals are never edited: every email address and
phone number is replaced by a stable token (email#xxxxxx / phone#xxxxxx, a short sha256 prefix, so
the same value always maps to the same token), and any verbatim dataset row longer than a short
fragment is replaced by "[dataset row omitted]". Case ids, user_N references, resource ids and
evidence ids are kept.

  python3 code/package.py              # writes ./code.zip and prints its listing and size

Excluded: dataset/, runs/, scratch/, .env, nested archives, __pycache__ / *.pyc, virtual
environments, .git. The build refuses to write a zip in which a key-shaped string (sk-...,
apikey_...) appears.
"""

import csv
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "code.zip"
EXCLUDED_DIRS = {
    "dataset",
    "runs",
    "scratch",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    ".pytest_cache",
}
EXCLUDED_NAMES = {".env", ".DS_Store"}
EXCLUDED_SUFFIXES = (".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".pyc", ".pyo")
KEY_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9])apikey_[A-Za-z0-9_-]{8,}"),
)
REPORT_COPIES = (
    "evaluation_report.md",
    "usage_report.md",
)  # also at evaluation/<name>, for either reading of the brief
DATA = ROOT / "dataset"
DOCS = [
    "docs/adr/*.md",
    "docs/01_CONTRACT.md",
    "docs/02_DATA_NOTES.md",
    "docs/02b_DOCS_AND_SCREENS.md",
    "docs/03_DESIGN.md",
    "docs/03_ID_RECOVERY_PROTOTYPE.md",
    "docs/LOSS_LEDGER.md",
    "docs/SILVER_AUDIT.md",
    "docs/silver_audit/*.md",
    "docs/JEV_SPIKE.md",
    "docs/JEV_HANDCHECK.md",
    "docs/JEV_REVIEW_QUEUE.md",
    "docs/BOARD.md",
]
EXTRA_DOCS = {"CONTEXT.md": "docs/CONTEXT.md"}
ROW_MIN = 80  # a dataset line at least this long is a "row", not a short quoted fragment
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"\+\d{1,3}[ (]*\d[\d ()-]{5,}\d")
TEL = re.compile(r"tel:\+?\d{6,}")
FIXED_TIME = (2026, 10, 25, 0, 0, 0)  # constant timestamps keep the zip byte-stable across builds


def key_hits(text):
    return [m.group(0)[:6] + "..." for p in KEY_PATTERNS for m in p.finditer(text)]


def files():
    out = [ROOT / "README.md"]
    for p in sorted((ROOT / "code").rglob("*")):
        rel = p.relative_to(ROOT)
        if (
            p.is_file()
            and not (set(rel.parts) & EXCLUDED_DIRS)
            and not any(
                part.startswith(".") for part in rel.parts[:-1]
            )  # tool caches (.ruff_cache)
            and p.name not in EXCLUDED_NAMES
            and not p.name.endswith(EXCLUDED_SUFFIXES)
        ):
            out.append(p)
    return out


def _identity_contacts(data_dir):
    """(emails, phones) from the identity snapshot and every value in the audit history."""
    emails, phones = set(), set()
    with open(data_dir / "user_identities.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            emails.add(r["email"])
            phones.add(r["phone"])
    with open(data_dir / "user_audit_log.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for v in (r["old_value"], r["new_value"]):
                if "@" in v:
                    emails.add(v)
                elif r["field_name"] == "phone":
                    phones.add(v)
    return emails, phones


def _dataset_rows(data_dir):
    """Every line of the text dataset files that is long enough to count as a row."""
    rows = set()
    for p in sorted(data_dir.rglob("*")):
        if p.is_file() and p.suffix in (".csv", ".sql", ".log", ".txt", ".json", ".jsonl"):
            for line in p.read_text(encoding="utf-8", errors="ignore").split("\n"):
                if len(line.strip()) >= ROW_MIN:
                    rows.add(line.strip())
    return rows


def identity_values(data_dir=DATA):
    """Every email and phone in the identity snapshot and the audit history, plus the verbatim
    dataset rows."""
    emails, phones = _identity_contacts(data_dir)
    return {
        "email": sorted(e for e in emails if e),
        "phone": sorted(p for p in phones if p),
        "rows": _dataset_rows(data_dir),
    }


def _token(kind, value):
    return f"{kind}#" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:6]


def _email_token(m):
    return _token("email", m.group(0).lower())


def _phone_token(m):
    return _token("phone", re.sub(r"\D", "", m.group(0)))


def sanitize(text, values):
    lines = []
    for line in text.split("\n"):
        segments = [line.strip()] + [
            x.strip().lstrip("-> ").strip("'\"") for x in re.split(r"`|\|", line)
        ]
        for seg in sorted(
            {x for x in segments if len(x) >= ROW_MIN and x in values["rows"]},
            key=len,
            reverse=True,
        ):
            line = line.replace(seg, "[dataset row omitted]")
        lines.append(line)
    text = "\n".join(lines)
    for v in sorted(
        values["phone"], key=len, reverse=True
    ):  # by value first: raw, then digits-only forms
        d = re.sub(r"\D", "", v)
        text = text.replace(v, _token("phone", d))
        if len(d) >= 8:
            text = re.sub(
                rf"(?<![0-9A-Za-z]){re.escape(d)}(?![0-9A-Za-z])", _token("phone", d), text
            )
    text = EMAIL.sub(_email_token, text)
    text = TEL.sub(_phone_token, text)
    return PHONE.sub(_phone_token, text)


def docs():
    """(published path, source path) for every doc that ships in code.zip."""
    out = []
    for pattern in DOCS:
        out += [(p.relative_to(ROOT).as_posix(), p) for p in sorted(ROOT.glob(pattern))]
    out += [(dst, ROOT / src) for src, dst in EXTRA_DOCS.items()]
    return sorted(out)


def build(out=OUT):
    entries = []
    for p in files():
        b = p.read_bytes()
        hits = key_hits(b.decode("utf-8", "ignore"))
        if hits:
            raise SystemExit(f"refusing to package: key-shaped string in {p.relative_to(ROOT)}")
        entries.append((p.relative_to(ROOT).as_posix(), b))
    by_name = dict(entries)
    entries += [(f"evaluation/{r}", by_name[f"code/evaluation/{r}"]) for r in REPORT_COPIES]
    values = identity_values()
    for name, src in docs():
        b = sanitize(src.read_text(encoding="utf-8"), values).encode("utf-8")
        if key_hits(b.decode("utf-8")):
            raise SystemExit(f"refusing to package: key-shaped string in {src.relative_to(ROOT)}")
        entries.append((name, b))
    out = Path(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, b in entries:
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, b)
    return out


def scan_repo():
    """Key-shaped strings in any git-tracked file (path and a masked prefix only)."""
    names = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=ROOT
    ).stdout.split("\n")
    hits = []
    for n in filter(None, names):
        p = ROOT / n
        if p.is_file():
            hits += [(n, h) for h in key_hits(p.read_bytes().decode("utf-8", "ignore"))]
    return hits


def main():
    out = build()
    with zipfile.ZipFile(out) as z:
        infos = z.infolist()
    for i in infos:
        print(f"{i.file_size:>9}  {i.filename}")
    print(
        f"{len(infos)} files, {sum(i.file_size for i in infos):,} bytes uncompressed, "
        f"{out.stat().st_size:,} bytes zipped -> {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

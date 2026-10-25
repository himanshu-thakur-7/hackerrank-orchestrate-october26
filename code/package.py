"""Build code.zip for submission: README.md and code/, plus evaluation/ holding copies of the two generated reports.

  python3 code/package.py              # writes ./code.zip and prints its listing and size

Excluded: dataset/, runs/, scratch/, .env, nested archives, __pycache__ / *.pyc, virtual environments, .git.
The build refuses to write a zip in which a key-shaped string (sk-..., apikey_...) appears.
"""
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "code.zip"
EXCLUDED_DIRS = {"dataset", "runs", "scratch", "__pycache__", ".venv", "venv", "node_modules", ".git", ".pytest_cache"}
EXCLUDED_NAMES = {".env", ".DS_Store"}
EXCLUDED_SUFFIXES = (".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".pyc", ".pyo")
KEY_PATTERNS = (re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}"), re.compile(r"(?<![A-Za-z0-9])apikey_[A-Za-z0-9_-]{8,}"))
REPORT_COPIES = ("evaluation_report.md", "usage_report.md")   # also at evaluation/<name>, for either reading of the brief
FIXED_TIME = (2026, 10, 25, 0, 0, 0)      # constant timestamps keep the zip byte-stable across builds


def key_hits(text):
    return [m.group(0)[:6] + "..." for p in KEY_PATTERNS for m in p.finditer(text)]


def files():
    out = [ROOT / "README.md"]
    for p in sorted((ROOT / "code").rglob("*")):
        rel = p.relative_to(ROOT)
        if p.is_file() and not (set(rel.parts) & EXCLUDED_DIRS) and p.name not in EXCLUDED_NAMES and not p.name.endswith(EXCLUDED_SUFFIXES):
            out.append(p)
    return out


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
    names = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=ROOT).stdout.split("\n")
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
    print(f"{len(infos)} files, {sum(i.file_size for i in infos):,} bytes uncompressed, {out.stat().st_size:,} bytes zipped -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Dataset overlay for metamorphic testing (T15): a full temporary copy of dataset/ that a relation edits,
then the real pipeline (`code/main.py`, as a subprocess) runs over it. dataset/ itself is never written.

  with Overlay(DATA) as ov:
      rows = ov.rows("deletion_requests.csv"); ...; ov.write_rows("deletion_requests.csv", rows)
      ov.add_evidence(file_id, rel_path, origin, captured_at, raw)   # also adds the manifest row
      out = ov.run()                                                 # {case_id: (status, steps)}
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "code" / "main.py"


def read_output(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(f)}


def run_pipeline(data_dir, out_path, requests=None, env=None):
    cmd = [sys.executable, str(MAIN), "--data", str(data_dir), "--out", str(out_path)]
    if requests:
        cmd += ["--requests", str(requests)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env={**os.environ, **(env or {})})
    if p.returncode != 0:
        raise RuntimeError(f"pipeline failed on {data_dir}:\n{p.stdout}\n{p.stderr}")
    return read_output(out_path)


def changed(a, b):
    """Case ids whose (status, steps) differ between two outputs (missing on one side counts as changed)."""
    return sorted((c for c in set(a) | set(b) if a.get(c) != b.get(c)), key=lambda c: (len(c), c))


class Overlay:
    def __init__(self, data_dir):
        self.src = Path(data_dir)
        self.root = None

    def __enter__(self):
        self._tmp = tempfile.mkdtemp(prefix="ghostaudit_overlay_")
        self.root = Path(self._tmp) / "dataset"
        shutil.copytree(self.src, self.root)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self._tmp, ignore_errors=True)
        return False

    def rows(self, name):
        with open(self.root / name, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def write_rows(self, name, rows, fieldnames=None):
        path = self.root / name
        raw = path.read_bytes()
        term = "\r\n" if b"\r\n" in raw[:4096] else "\n"
        fields = fieldnames or next(csv.reader(io.StringIO(raw.decode("utf-8"))))
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, lineterminator=term)
        w.writeheader()
        w.writerows(rows)
        path.write_text(buf.getvalue(), encoding="utf-8", newline="")

    def add_evidence(self, file_id, rel_path, origin, captured_at, raw):
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        m = self.rows("evidence_files.csv")
        m.append({"file_id": file_id, "file_path": rel_path, "origin": origin, "captured_at": captured_at})
        self.write_rows("evidence_files.csv", m)

    def remove_evidence(self, file_id):
        m = self.rows("evidence_files.csv")
        row = next(r for r in m if r["file_id"] == file_id)
        (self.root / row["file_path"]).unlink()
        self.write_rows("evidence_files.csv", [r for r in m if r["file_id"] != file_id])
        return row

    def run(self, requests="deletion_requests.csv", env=None):
        return run_pipeline(self.root, Path(self._tmp) / "out.csv", self.root / requests, env)

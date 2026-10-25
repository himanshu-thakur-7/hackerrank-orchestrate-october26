"""Run history: every evaluated run is kept under runs/<UTC timestamp>/ with
metrics.json, output.csv and commit (the git HEAD at run time), so regressions can be diffed.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from evaluation import scorer


def record(runs_dir, output_path, metrics, commit, ts=None):
    ts = ts or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    d = Path(runs_dir) / ts
    d.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(output_path, d / "output.csv")
    (d / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (d / "commit").write_text(commit + "\n", encoding="utf-8")
    return d


def previous(runs_dir, run_dir):
    older = sorted(p for p in Path(runs_dir).iterdir() if p.is_dir() and p.name < Path(run_dir).name)
    return older[-1] if older else None


def diff(prev_output, cur_output):
    a, b = scorer.load(prev_output), scorer.load(cur_output)
    key = lambda s: (s["phase"], s["system_id"], s["resource_id"], s["operation"], s["state"], s["evidence_id"] or "-")
    out = []
    for c in sorted(set(a) | set(b), key=lambda x: (x.rpartition("_")[0], int(x.rpartition("_")[2]) if x.rpartition("_")[2].isdigit() else -1)):
        sa, ta = a.get(c, ("(absent)", []))
        sb, tb = b.get(c, ("(absent)", []))
        if sa != sb:
            out.append(f"{c}: status {sa} -> {sb}")
        ka, kb = [key(s) for s in ta], [key(s) for s in tb]
        out += [f"{c}: - {' '.join(k)}" for k in ka if k not in kb]
        out += [f"{c}: + {' '.join(k)}" for k in kb if k not in ka]
    return out

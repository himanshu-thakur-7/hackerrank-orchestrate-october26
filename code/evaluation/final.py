"""T14 final validation: every gate in one command, then a clean-room run of the packaged code.

  python3 code/evaluation/main.py final

Steps (each runs as its own subprocess, so no state leaks between them): unit tests, contract gate,
determinism, invariants, metamorphic relations, custom cases, literal audit, selftest, sample
scores, the usage report (its measured run must equal output.csv), the package build and a key scan,
and the clean room: unzip code.zip into an empty temp directory and run it there against dataset/
with OPENAI_API_KEY and TYPESAFE_API_KEY removed from the environment; output.csv must have the same
sha256.
"""

import contextlib
import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"
KEYS = ("OPENAI_API_KEY", "TYPESAFE_API_KEY")
EVAL = [sys.executable, str(ROOT / "code" / "evaluation" / "main.py")]
STEPS = [
    (
        "unit tests (solver)",
        [sys.executable, "-m", "unittest", "discover", "-s", "code/tests", "-t", "code/tests"],
    ),
    (
        "unit tests (evaluation)",
        [sys.executable, "-m", "unittest", "discover", "-s", "code/evaluation/tests", "-t", "code"],
    ),
    ("contract gate", EVAL + ["contract"]),
    ("determinism", EVAL + ["determinism"]),
    ("invariants", EVAL + ["invariants"]),
    ("metamorphic", EVAL + ["metamorphic"]),
    ("custom cases", EVAL + ["custom"]),
    ("literal audit", EVAL + ["audit"]),
    ("selftest", EVAL + ["selftest"]),
    ("usage report", EVAL + ["usage"]),
]


OPTIONAL = (
    "pandas",
    "openai",
    "pypdf",
    "typesafe_sdk",
    "pdftotext",
)  # the last one is an executable, the rest modules
SITECUSTOMIZE = """import importlib.machinery, os, sys
# "Not installed": the copy in site-packages/dist-packages is hidden. None in sys.modules makes
# `import m` raise ModuleNotFoundError and importlib.util.find_spec(m) return None. A module a test
# puts on PYTHONPATH still imports.
_local = [p for p in sys.path if "site-packages" not in p and "dist-packages" not in p]
for _m in filter(None, os.environ.get("GHOSTAUDIT_BLOCK_MODULES", "").split(",")):
    if importlib.machinery.PathFinder.find_spec(_m, _local) is None:
        sys.modules[_m] = None
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _here]
del sys.modules["sitecustomize"]
try:                                   # chain to the interpreter's own sitecustomize, if any
    import sitecustomize  # noqa: F401
except ImportError:
    pass
"""


def blocked_env(block, base=None):
    """An environment in which the given optional modules fail to import (also in child processes)
    and the
    given executables are not on PATH. Keys are removed as well, so the unit tests see a no-key
    machine."""
    env = dict(os.environ if base is None else base)
    for k in KEYS:
        env.pop(k, None)
    d = Path(tempfile.mkdtemp(prefix="ghostaudit_block_"))
    (d / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    env["GHOSTAUDIT_BLOCK_MODULES"] = ",".join(m for m in block if m != "pdftotext")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(d)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    )
    if "pdftotext" in block:  # a shadow PATH: every executable except pdftotext
        shadow = d / "bin"
        shadow.mkdir()
        for folder in env.get("PATH", "").split(os.pathsep):
            if not folder or not Path(folder).is_dir():
                continue
            for exe in Path(folder).iterdir():
                if exe.name != "pdftotext" and not (shadow / exe.name).exists():
                    with contextlib.suppress(OSError):
                        (shadow / exe.name).symlink_to(exe)
        env["PATH"] = str(shadow)
    return env


def matrix_configs():
    return [(m,) for m in OPTIONAL] + [OPTIONAL]


def matrix(workers=4):
    """Both unit-test suites once per config (each optional dependency blocked alone, then all), in
    parallel.
    The suites write only to their own temp dirs, so concurrent configs cannot interfere."""
    from concurrent.futures import ThreadPoolExecutor

    jobs = [(block, name, cmd) for block in matrix_configs() for name, cmd in STEPS[:2]]

    def one(job):
        block, name, cmd = job
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env=blocked_env(block))
        label = f"matrix [{'all blocked' if len(block) > 1 else block[0] + ' blocked'}] {name}"
        fails = [line for line in p.stderr.split("\n") if line.startswith(("FAIL:", "ERROR:"))]
        return (
            label,
            p.returncode,
            _last(p.stderr) + (" | " + "; ".join(fails[:4]) if fails else ""),
        )

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, jobs))
    for label, code, last in results:
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {label}: {last}")
    return results


def _env_without_keys():
    return {k: v for k, v in os.environ.items() if k not in KEYS}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def clean_room(data_dir=DATA):
    """Build code.zip into a temp dir, unzip it into another empty one and run code/main.py there
    with no keys."""
    sys.path.insert(0, str(ROOT / "code"))
    import package

    base = Path(tempfile.mkdtemp(prefix="ghostaudit_cleanroom_"))
    z = package.build(base / "code.zip")
    work = base / "unzipped"
    work.mkdir()
    with zipfile.ZipFile(z) as f:
        f.extractall(work)
    env = _env_without_keys()
    p = subprocess.run(
        [
            sys.executable,
            "-I",
            str(work / "code" / "main.py"),
            "--data",
            str(Path(data_dir).resolve()),
            "--out",
            str(work / "output.csv"),
        ],
        capture_output=True,
        text=True,
        cwd=work,
        env=env,
    )
    sha = _sha(work / "output.csv") if (work / "output.csv").exists() else ""
    return {
        "ok": p.returncode == 0 and sha == _sha(ROOT / "output.csv"),
        "sha256": sha,
        "returncode": p.returncode,
        "keys_in_env": any(k in env for k in KEYS),
        "workdir": str(work),
        "files": len(zipfile.ZipFile(z).namelist()),
        "stderr": p.stderr[-1500:],
    }


def summarize(results):
    rows = [(name, "PASS" if code == 0 else "FAIL", last) for name, code, last in results]
    return all(code == 0 for _, code, _ in results), rows


def _last(text):
    lines = [line for line in text.strip().split("\n") if line.strip()]
    return lines[-1].strip() if lines else ""


def scores():
    """Headline sample metrics (dev / holdout aggregate / all) for the final table."""
    sys.path.insert(0, str(ROOT / "code"))
    from evaluation import scorer, split

    out = Path(tempfile.mkdtemp(prefix="ghostaudit_final_")) / "sample_pred.csv"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "code" / "main.py"),
            "--requests",
            str(DATA / "sample_deletion_requests.csv"),
            "--out",
            str(out),
        ],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        env=_env_without_keys(),
    )
    gold, pred = scorer.load(DATA / "sample_output.csv"), scorer.load(out)
    dev, hold, _ = split.load_frozen()
    return {
        name: scorer.score(pred, gold, ids)
        for name, ids in (("dev", dev), ("holdout", hold), ("all", dev + hold))
    }


def run(with_matrix=False):
    results = []
    for name, cmd in STEPS:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        results.append(
            (
                name,
                p.returncode,
                _last(p.stdout + "\n" + p.stderr if name.startswith("unit") else p.stdout),
            )
        )
        print(f"  {'PASS' if p.returncode == 0 else 'FAIL'}  {name}: {results[-1][2]}")
    sys.path.insert(0, str(ROOT / "code"))
    import package

    hits = package.scan_repo()
    results.append(
        ("key scan (repo)", 1 if hits else 0, f"{len(hits)} key-shaped string(s) in tracked files")
    )
    print(f"  {'PASS' if not hits else 'FAIL'}  key scan (repo): {results[-1][2]}")
    if with_matrix:
        results += matrix()
    cr = clean_room()
    results.append(
        (
            "clean room",
            0 if cr["ok"] else 1,
            f"{cr['files']} files unzipped into an empty dir, keys unset; "
            f"output.csv sha256 {cr['sha256'][:12]} (committed {_sha(ROOT / 'output.csv')[:12]})",
        )
    )
    print(f"  {'PASS' if cr['ok'] else 'FAIL'}  clean room: {results[-1][2]}")
    if not cr["ok"]:
        print(cr["stderr"])
    m = scores()
    keys = (
        "status_accuracy",
        "finding_f1",
        "policy_accuracy",
        "evidence_accuracy",
        "strict_step_f1",
        "field_acc_mean",
        "sequence_exact",
        "sequence_lcs_mean",
        "row_exact",
        "proxy",
    )
    print("\nFINAL SCORES (32 labeled samples; holdout is aggregate only)")
    print(f"  {'metric':20} {'dev':>7} {'holdout':>8} {'all':>7}")
    for k in keys:
        print(f"  {k:20} {m['dev'][k]:7.3f} {m['holdout'][k]:8.3f} {m['all'][k]:7.3f}")
    ok, rows = summarize(results)
    print(
        f"\nFINAL VALIDATION: {'GREEN' if ok else 'RED'} "
        f"({sum(r[1] == 'PASS' for r in rows)}/{len(rows)} steps pass)"
    )
    return 0 if ok else 1

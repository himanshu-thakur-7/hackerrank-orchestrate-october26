"""Code-quality metrics for code/: complexity, docstrings, annotations, lint, types, tests.

  python3 code/evaluation/main.py quality

Standard-library measures always run: cyclomatic complexity (an ast counter with radon's rules, so
no dependency is needed), docstring coverage (every module, naming its ADR, and every public class
and function), annotation coverage (every function's arguments and return) and the unit-test
counts. Dev tools are optional: ruff findings, mypy errors (strict for ghostaudit, main and package;
the default profile for evaluation) and per-module branch coverage of ghostaudit each print SKIPPED
when the tool is not installed, and a skipped tool never fails the command.

The command fails (exit 1) when a measured value breaks a limit: complexity above COMPLEXITY_LIMIT
(ghostaudit, main, package) or EVALUATION_COMPLEXITY_LIMIT (evaluation), any missing docstring or
annotation, any ruff finding or mypy error, or a ghostaudit module under COVERAGE_FLOOR.

Decisions: ADR: none (developer tooling; nothing here feeds output.csv).
"""

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
COMPLEXITY_LIMIT = 10  # radon grade B: ghostaudit, main.py, package.py (ruff C901 enforces it)
EVALUATION_COMPLEXITY_LIMIT = 15  # radon grade C: the evaluation harness (evaluation/ruff.toml)
COVERAGE_FLOOR = 85  # percent branch coverage per ghostaudit module, from the solver tests
GENERATED = {"llm_cache.py", "pdf_text_cache.py", "screens_data.py", "jev_cache.py"}
ADR_LINE = re.compile(r"ADR \d{4}|ADR: none")


def sources(code_dir, part):
    """The hand-written .py files of one part of code/: 'solver' (ghostaudit, main.py,
    package.py) or 'evaluation' (the harness, its tests and fixtures excluded)."""
    d = Path(code_dir)
    if part == "solver":
        files = sorted((d / "ghostaudit").rglob("*.py")) + [d / "main.py", d / "package.py"]
    else:
        files = [
            p
            for p in sorted((d / "evaluation").rglob("*.py"))
            if not {"tests", "fixtures"} & set(p.relative_to(d).parts)
        ]
    return [p for p in files if p.is_file() and p.name not in GENERATED]


class _Complexity(ast.NodeVisitor):
    """Decision points of one block, counted like radon; nested functions are their own blocks."""

    def __init__(self):
        self.n = 0

    def generic_visit(self, node):
        if isinstance(node, ast.Try | getattr(ast, "TryStar", ast.Try)):
            self.n += len(node.handlers) + bool(node.orelse)
        elif isinstance(node, ast.BoolOp):
            self.n += len(node.values) - 1
        elif isinstance(node, ast.If | ast.IfExp | ast.Assert):
            self.n += 1
        elif isinstance(node, ast.Match):
            wildcard = any(getattr(c.pattern, "pattern", False) is None for c in node.cases)
            self.n += max(0, len(node.cases) - wildcard)
        elif isinstance(node, ast.For | ast.AsyncFor | ast.While):
            self.n += 1 + bool(node.orelse)
        elif isinstance(node, ast.comprehension):
            self.n += 1 + len(node.ifs)
        super().generic_visit(node)

    def visit_FunctionDef(self, node):
        """A nested function adds nothing to the enclosing block (radon's rule)."""

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef


def _functions(tree):
    """(qualified name, node) of every function and method, nested ones included (also those
    defined inside a loop or a branch of the enclosing function)."""
    out = []

    def walk(node, prefix):
        for n in ast.iter_child_nodes(node):
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef):
                out.append((prefix + n.name, n))
                walk(n, prefix + n.name + ".")
            elif isinstance(n, ast.ClassDef):
                walk(n, prefix + n.name + ".")
            else:
                walk(n, prefix)

    walk(tree, "")
    return out


def _public_definitions(tree):
    """(qualified name, node) of the module's public classes and functions and the public
    members of its public classes (function bodies are not searched)."""
    out = []

    def walk(node, prefix):
        for n in ast.iter_child_nodes(node):
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if not n.name.startswith("_") and not prefix.startswith("_"):
                    out.append((prefix + n.name, n))
                if isinstance(n, ast.ClassDef):
                    walk(n, prefix + n.name + ".")

    walk(tree, "")
    return out


def complexity(paths):
    """[(path, qualified name, cyclomatic complexity)] of every function in `paths`."""
    out = []
    for p in paths:
        for name, fn in _functions(ast.parse(Path(p).read_text(encoding="utf-8"))):
            v = _Complexity()
            for child in fn.body:
                v.visit(child)
            out.append((str(p), name, 1 + v.n))
    return out


def docstrings(paths):
    """(documented, total, missing) over every module and every public class and function.

    A module counts only when its docstring names its ADR ('ADR NNNN' or 'ADR: none')."""
    documented, total, missing = 0, 0, []
    for p in paths:
        tree = ast.parse(Path(p).read_text(encoding="utf-8"))
        total += 1
        if ADR_LINE.search(ast.get_docstring(tree) or ""):
            documented += 1
        else:
            missing.append(f"{p}:1 module")
        for name, n in _public_definitions(tree):
            total += 1
            if ast.get_docstring(n):
                documented += 1
            else:
                missing.append(f"{p}:{n.lineno} {name}")
    return documented, total, missing


def _annotated(fn, in_class):
    args = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
    if in_class and args and args[0].arg in ("self", "cls"):
        args = args[1:]
    extra = [a for a in (fn.args.vararg, fn.args.kwarg) if a is not None]
    return fn.returns is not None and all(a.annotation is not None for a in args + extra)


def annotations(paths):
    """(annotated, total, missing) over every function: all arguments (self and cls aside) and
    the return must be annotated."""
    annotated, total, missing = 0, 0, []
    for p in paths:
        tree = ast.parse(Path(p).read_text(encoding="utf-8"))
        methods = {id(f) for c in ast.walk(tree) if isinstance(c, ast.ClassDef) for f in c.body}
        for name, fn in _functions(tree):
            total += 1
            if _annotated(fn, id(fn) in methods):
                annotated += 1
            else:
                missing.append(f"{p}:{fn.lineno} {name}")
    return annotated, total, missing


def tool(cmd, cwd=None):
    """Run a dev tool and return (exit code, stdout); None when it is not installed."""
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    p = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout


def ruff_findings(code_dir):
    """Number of ruff findings over code/ with the committed configuration; None if absent."""
    r = tool(["ruff", "check", "--output-format", "json", "--quiet", "."], cwd=code_dir)
    return None if r is None else len(json.loads(r[1] or "[]"))


def _mypy_errors(args, cwd, prefix=""):
    """Error lines mypy reports for files whose path starts with `prefix`; None if absent."""
    r = tool(["mypy", "--no-error-summary", *args], cwd=cwd)
    if r is None:
        return None
    return sum(1 for line in r[1].splitlines() if line.startswith(prefix) and ": error:" in line)


def mypy_errors(code_dir):
    """(strict errors: ghostaudit, main, package; default-profile errors in evaluation/ files);
    None for each when mypy is absent. The second run follows imports into ghostaudit, so only
    lines in evaluation/ count there."""
    return _mypy_errors([], code_dir), _mypy_errors(["evaluation"], code_dir, "evaluation/")


def test_counts(code_dir):
    """Unit tests found by unittest discovery: {'solver': n, 'evaluation': n}."""
    d = Path(code_dir)
    loader = unittest.TestLoader()
    solver = loader.discover(str(d / "tests"), top_level_dir=str(d / "tests")).countTestCases()
    sys.path.insert(0, str(d))
    evaluation = loader.discover(str(d / "evaluation" / "tests"), top_level_dir=str(d))
    return {"solver": solver, "evaluation": evaluation.countTestCases()}


def coverage(code_dir):
    """{module: branch coverage %} of ghostaudit from the solver tests; None without coverage.py.

    The data file lives in a temp dir, so nothing is written under code/."""
    if importlib.util.find_spec("coverage") is None:
        return None
    d = Path(code_dir)
    tmp = Path(tempfile.mkdtemp(prefix="ghostaudit_cov_"))
    env = {**os.environ, "COVERAGE_FILE": str(tmp / ".coverage")}
    run = [sys.executable, "-m", "coverage"]
    try:
        subprocess.run(
            run
            + ["run", "--branch", "--source=ghostaudit", "-m", "unittest", "discover"]
            + ["-s", "tests", "-t", "tests"],
            cwd=d,
            env=env,
            capture_output=True,
            check=True,
        )
        omit = ",".join(f"*/{g}" for g in sorted(GENERATED))
        subprocess.run(
            run + ["json", "-o", str(tmp / "cov.json"), f"--omit={omit}"],
            cwd=d,
            env=env,
            capture_output=True,
            check=True,
        )
        data = json.loads((tmp / "cov.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {
        Path(f).as_posix(): round(v["summary"]["percent_covered"])
        for f, v in sorted(data["files"].items())
    } | {"TOTAL": round(data["totals"]["percent_covered"])}


def collect(code_dir=CODE, with_coverage=True):
    """Every quality metric of the tree at `code_dir` (dev-tool metrics are None when absent)."""
    solver, evaluation = sources(code_dir, "solver"), sources(code_dir, "evaluation")
    cc_solver = complexity(solver)
    cc_eval = complexity(evaluation)
    doc_s, doc_e = docstrings(solver), docstrings(evaluation)
    ann = annotations(solver)
    strict, relaxed = mypy_errors(code_dir)
    cov = coverage(code_dir) if with_coverage else None
    modules = {k: v for k, v in (cov or {}).items() if k != "TOTAL"}
    return {
        "complexity_max": max(n for *_, n in cc_solver),
        "complexity_max_evaluation": max(n for *_, n in cc_eval),
        "complexity_over": [f"{p} {q} {n}" for p, q, n in cc_solver if n > COMPLEXITY_LIMIT]
        + [f"{p} {q} {n}" for p, q, n in cc_eval if n > EVALUATION_COMPLEXITY_LIMIT],
        "docstrings": doc_s[:2],
        "docstrings_evaluation": doc_e[:2],
        "docstrings_missing": doc_s[2] + doc_e[2],
        "annotations": ann[:2],
        "annotations_missing": ann[2],
        "ruff_findings": ruff_findings(code_dir),
        "mypy_errors": strict,
        "mypy_relaxed_errors": relaxed,
        "tests": test_counts(code_dir),
        "coverage": cov,
        "coverage_min": min(modules.values()) if modules else None,
        "coverage_total": cov["TOTAL"] if cov else None,
    }


def _pct(pair):
    done, total = pair
    return f"{done}/{total} ({100 * done / total:.0f}%)" if total else "0/0"


def render_tools(m):
    """Report lines for the dev-tool metrics; SKIPPED when the tool is not installed."""

    def show(value, text):
        return "SKIPPED (not installed)" if value is None else text

    cov = m["coverage_min"]
    return [
        f"  ruff findings              {show(m['ruff_findings'], str(m['ruff_findings']))}",
        f"  mypy errors (strict)       {show(m['mypy_errors'], str(m['mypy_errors']))}",
        "  mypy errors (evaluation)   "
        + show(m["mypy_relaxed_errors"], str(m["mypy_relaxed_errors"])),
        "  coverage, ghostaudit       "
        + show(cov, f"{m['coverage_total']}% total, lowest module {cov}%"),
    ]


def failures(m):
    """Every limit the metrics break (an empty list passes)."""
    out = list(m["complexity_over"]) + list(m["docstrings_missing"])
    out += [f"unannotated {x}" for x in m["annotations_missing"]]
    if m["ruff_findings"]:
        out.append(f"ruff: {m['ruff_findings']} finding(s)")
    if m["mypy_errors"] or m["mypy_relaxed_errors"]:
        out.append(f"mypy: {m['mypy_errors']} strict / {m['mypy_relaxed_errors']} evaluation")
    out += [
        f"coverage {k} {v}% < {COVERAGE_FLOOR}%"
        for k, v in (m["coverage"] or {}).items()
        if k != "TOTAL" and v < COVERAGE_FLOOR
    ]
    return out


def run(code_dir=CODE):
    """`main.py quality`: print every metric; exit 1 when a measured value breaks a limit."""
    m = collect(code_dir)
    t = m["tests"]
    print("CODE QUALITY (code/)")
    print(
        f"  max cyclomatic complexity  {m['complexity_max']} solver (limit {COMPLEXITY_LIMIT}), "
        f"{m['complexity_max_evaluation']} evaluation (limit {EVALUATION_COMPLEXITY_LIMIT})"
    )
    print(
        f"  docstrings                 {_pct(m['docstrings'])} solver, "
        f"{_pct(m['docstrings_evaluation'])} evaluation"
    )
    print(f"  annotations                {_pct(m['annotations'])} solver functions")
    print(f"  unit tests                 {t['solver']} solver, {t['evaluation']} evaluation")
    for line in render_tools(m):
        print(line)
    bad = failures(m)
    for x in bad[:20]:
        print(f"  FAIL {x}")
    print(f"QUALITY: {'OK' if not bad else f'{len(bad)} problem(s)'}")
    return 0 if not bad else 1

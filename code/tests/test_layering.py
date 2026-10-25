"""Layering of the solver package: what ghostaudit may import, and when.

* ghostaudit never imports the evaluation harness (evaluation imports ghostaudit, not back);
* the default path imports no optional dependency at import time (openai, typesafe-sdk, pandas
  and pypdf are imported lazily, only where a feature needs them; ADR 0008, 0013);
* module-level imports inside ghostaudit form no cycle.
"""

import ast
import subprocess
import sys
import unittest

from _path import CODE

PACKAGE = CODE / "ghostaudit"
OPTIONAL = ("openai", "typesafe_sdk", "pandas", "pypdf")


def _modules():
    """{dotted module name: path} for every module of the ghostaudit package."""
    out = {}
    for p in sorted(PACKAGE.rglob("*.py")):
        parts = p.relative_to(CODE).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        out[name] = p
    return out


def _imports(tree, top_level_only, modules=()):
    """Dotted names a module imports; top_level_only skips lazy (function-level) imports and
    TYPE_CHECKING blocks, which never run at import time. `from pkg import sub` names the
    submodule `pkg.sub` when it is one of `modules`, else `pkg`."""
    nodes = tree.body if top_level_only else list(ast.walk(tree))
    out = []
    for n in nodes:
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            subs = [f"{n.module}.{a.name}" for a in n.names]
            out += [s if s in modules else n.module for s in subs]
    return out


class Layering(unittest.TestCase):
    def test_ghostaudit_never_imports_the_evaluation_harness(self):
        for name, path in _modules().items():
            for imported in _imports(ast.parse(path.read_text(encoding="utf-8")), False):
                self.assertFalse(
                    imported == "evaluation" or imported.startswith("evaluation."),
                    f"{name} imports {imported}",
                )

    def test_default_path_imports_no_optional_dependency(self):
        mods = sorted(_modules())
        probe = (
            "import importlib, sys\n"
            f"sys.path.insert(0, {str(CODE)!r})\n"
            f"for m in {mods!r} + ['main']:\n"
            "    importlib.import_module(m)\n"
            f"print(sorted(m for m in sys.modules if m.split('.')[0] in {OPTIONAL!r}))\n"
        )
        p = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "[]")

    def test_module_level_imports_have_no_cycle(self):
        mods = _modules()
        graph = {
            name: sorted(
                {
                    i
                    for i in _imports(ast.parse(p.read_text(encoding="utf-8")), True, mods)
                    if i in mods
                }
                - {name}
            )
            for name, p in mods.items()
        }
        state = {}

        def visit(node, path):
            state[node] = "open"
            for nxt in graph[node]:
                self.assertNotEqual(state.get(nxt), "open", " -> ".join(path + [nxt]))
                if nxt not in state:
                    visit(nxt, path + [nxt])
            state[node] = "done"

        for name in sorted(graph):
            if name not in state:
                visit(name, [name])


if __name__ == "__main__":
    unittest.main()

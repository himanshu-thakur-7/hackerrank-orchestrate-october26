"""The README promises Python 3.11+: every module under code/ must compile on the oldest interpreter present."""

import shutil
import subprocess
import unittest
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
OLDEST = ("python3.11",)
SCRIPT = (
    "import pathlib, sys\n"
    "bad = []\n"
    "for p in sorted(pathlib.Path(sys.argv[1]).rglob('*.py')):\n"
    "    try:\n        compile(p.read_text(encoding='utf-8'), str(p), 'exec')\n"
    "    except SyntaxError as e:\n        bad.append(f'{p}:{e.lineno}: {e.msg}')\n"
    "print('\\n'.join(bad) or 'ALL COMPILE')\n"
)


class OldestPython(unittest.TestCase):
    def test_every_module_compiles_on_python_3_11(self):
        exe = next((shutil.which(e) for e in OLDEST if shutil.which(e)), None)
        if exe is None:
            self.skipTest("python3.11 is not installed here")
        p = subprocess.run([exe, "-I", "-c", SCRIPT, str(CODE)], capture_output=True, text=True)
        self.assertEqual(p.stdout.strip(), "ALL COMPILE", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()

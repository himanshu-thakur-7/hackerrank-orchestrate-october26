import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
ROOT = CODE.parent
DATA = ROOT / "dataset"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

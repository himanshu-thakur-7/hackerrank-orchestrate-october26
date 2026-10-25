"""Plain CSV loading for the participant-facing dataset files (stdlib only)."""

from __future__ import annotations

import csv
from pathlib import Path


# A request row of deletion_requests.csv (all values are strings).
Request = dict[str, str]


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_requests(path: str | Path) -> list[Request]:
    return read_csv(Path(path))

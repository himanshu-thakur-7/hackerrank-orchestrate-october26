"""Plain CSV loading for the participant-facing dataset files (stdlib only).

Decisions: ADR: none (plain reading; the input contract is AGENTS.md §6.2)."""

from __future__ import annotations

import csv
from pathlib import Path

# A request row of deletion_requests.csv (all values are strings).
Request = dict[str, str]


def read_csv(path: str | Path) -> list[dict[str, str]]:
    """Every row of a UTF-8 CSV file as a dict of strings, in file order."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_requests(path: str | Path) -> list[Request]:
    """The requests of a deletion_requests.csv-shaped file, in file order."""
    return read_csv(Path(path))

"""Plain CSV loading for the participant-facing dataset files (stdlib only)."""

import csv
from pathlib import Path


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_requests(path):
    return read_csv(Path(path))

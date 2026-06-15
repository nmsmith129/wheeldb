"""Test-only helpers for reading CSV output back for round-trip assertions.

These live under ``tests/`` so the CSV round-trip tests share one reader rather
than re-implementing ``csv`` parsing in each test (mirrors the role of
:mod:`print_helpers`). They read with the same dialect the store writes
(stdlib ``csv``, UTF-8, ``newline=""``) so embedded commas/quotes/newlines
round-trip faithfully.
"""

from __future__ import annotations

import csv
from pathlib import Path


def read_header(path) -> list[str]:
    """Return the header row of a CSV file as a list of column names.

    Parameters:
        path: filesystem path to the CSV file to read.
    Returns:
        The first row's fields, or ``[]`` if the file is empty.
    """
    with open(Path(path), newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            return row
    return []


def read_csv_rows(path) -> list[dict]:
    """Return the data rows of a CSV file as a list of dicts keyed by column name.

    Parameters:
        path: filesystem path to the CSV file to read.
    Returns:
        One dict per data row (header excluded), each mapping column name to the
        cell's string value exactly as read back.
    """
    with open(Path(path), newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

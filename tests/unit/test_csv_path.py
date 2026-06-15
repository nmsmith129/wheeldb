"""Unit tests for the CSV output-path derivation helper (``wheeldb.cli``).

The ``--format csv`` run derives its output path from the existing ``--db`` path
by swapping the extension to ``.csv`` (FR-002a). Debug output prints each
input -> output mapping at the point of failure (Constitution Principle V).
"""

from __future__ import annotations

from wheeldb.cli import _csv_output_path


def test_swaps_sqlite_extension_for_csv():
    """A .sqlite path becomes the same name with a .csv extension."""
    result = _csv_output_path("wheeldb.sqlite")
    print(f"wheeldb.sqlite -> {result}")
    assert result == "wheeldb.csv"


def test_appends_csv_when_no_extension():
    """A path with no extension has .csv appended."""
    result = _csv_output_path("wheeldb")
    print(f"wheeldb -> {result}")
    assert result == "wheeldb.csv"


def test_replaces_only_final_dotted_segment():
    """Only the final dotted segment (the recognized extension) is replaced."""
    result = _csv_output_path("my.data.sqlite")
    print(f"my.data.sqlite -> {result}")
    assert result == "my.data.csv"

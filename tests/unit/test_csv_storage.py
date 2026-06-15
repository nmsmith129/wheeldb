"""Unit tests for the CSV persistence layer (``wheeldb.csv_storage``).

Covers the container basics (open/empty, header-only commit, transaction
rollback, counts) for the foundational phase, then upsert/serialization (US1)
and existing-file load + idempotency + header validation (US2). Tests run
against throwaway ``tmp_path`` files. Debug output prints the expected vs actual
header/rows at the point of failure (Constitution Principle V).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))  # for csv_helpers
from csv_helpers import read_csv_rows, read_header  # noqa: E402

from wheeldb.csv_storage import CsvPuzzleStore
from wheeldb.errors import DatabaseError
from wheeldb.models import Puzzle, PuzzleParseError

#: The canonical CSV header, in order (FR-003).
EXPECTED_HEADER = [
    "season",
    "episode",
    "date",
    "puzzle_type",
    "puzzle_number",
    "category",
    "solution",
    "flags",
]


def _sample_puzzle(**overrides):
    """Build a Puzzle with sensible defaults for CSV row tests.

    Parameters:
        overrides: attribute values to override on the default puzzle.
    Returns:
        A ``Puzzle`` instance.
    """
    base = dict(
        solution="OPENING NIGHT",
        category="Show Biz",
        date="2024-09-09",
        season=42,
        episode=8011,
        round="T1",
        flags=(),
    )
    base.update(overrides)
    return Puzzle(**base)


# --- Foundational: container (T002) -------------------------------------------

def test_open_absent_path_is_empty(tmp_path):
    """Opening an absent CSV path yields an empty store (no file created yet)."""
    csv_path = tmp_path / "out.csv"
    with CsvPuzzleStore(csv_path) as store:
        print(f"count={store.count()}; exists={csv_path.exists()}")
        assert store.count() == 0
        assert store.count_for_season(42) == 0


def test_commit_empty_store_writes_header_only(tmp_path):
    """Committing an empty store writes a valid header-only file (zero-puzzle edge)."""
    csv_path = tmp_path / "out.csv"
    with CsvPuzzleStore(csv_path) as store:
        with store.transaction():
            pass  # no upserts
    header = read_header(csv_path)
    rows = read_csv_rows(csv_path)
    print(f"header={header}; data rows={rows}")
    assert header == EXPECTED_HEADER
    assert rows == []


def test_transaction_rolls_back_on_exception(tmp_path):
    """An exception inside transaction() restores the prior state and re-raises."""
    csv_path = tmp_path / "out.csv"
    with CsvPuzzleStore(csv_path) as store:
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.upsert(_sample_puzzle())
                raise RuntimeError("boom")
        print(f"count after rollback={store.count()}")
        assert store.count() == 0


def test_empty_file_opens_as_no_data(tmp_path):
    """A zero-byte file is treated as 'no prior data', not a header mismatch."""
    csv_path = tmp_path / "out.csv"
    csv_path.write_text("", encoding="utf-8")
    with CsvPuzzleStore(csv_path) as store:
        print(f"count={store.count()} for empty file")
        assert store.count() == 0


# --- US1: upsert / serialization (T004) ---------------------------------------

def test_upsert_added_then_serialized_columns_in_order(tmp_path):
    """Upserting a new puzzle returns 'added' and writes the columns in order."""
    csv_path = tmp_path / "out.csv"
    puzzle = _sample_puzzle(round="R2", flags=(("date", "*"),))
    with CsvPuzzleStore(csv_path) as store:
        with store.transaction():
            result = store.upsert(puzzle)
    rows = read_csv_rows(csv_path)
    print(f"result={result}; header={read_header(csv_path)}; rows={rows}")
    assert result == "added"
    assert read_header(csv_path) == EXPECTED_HEADER
    assert len(rows) == 1
    row = rows[0]
    assert row == {
        "season": "42", "episode": "8011", "date": "2024-09-09",
        "puzzle_type": "Round", "puzzle_number": "2",
        "category": "Show Biz", "solution": "OPENING NIGHT",
        "flags": '[["date", "*"]]',
    }


def test_upsert_empty_flags_serialize_to_empty_json_array(tmp_path):
    """A puzzle with no flags stores ``[]``; date written verbatim, ints as text."""
    csv_path = tmp_path / "out.csv"
    with CsvPuzzleStore(csv_path) as store:
        with store.transaction():
            store.upsert(_sample_puzzle())
    row = read_csv_rows(csv_path)[0]
    print(f"row={row}")
    assert row["flags"] == "[]"
    assert row["date"] == "2024-09-09"
    assert row["puzzle_number"] == "0" or row["puzzle_number"] == "1"  # T1 -> 1


def test_special_characters_round_trip(tmp_path):
    """Commas, quotes, and embedded newlines round-trip back to the exact value (FR-007)."""
    csv_path = tmp_path / "out.csv"
    tricky_category = 'Quote, "inside", end'
    tricky_solution = "LINE ONE\nLINE TWO"
    puzzle = _sample_puzzle(category=tricky_category, solution=tricky_solution)
    with CsvPuzzleStore(csv_path) as store:
        with store.transaction():
            store.upsert(puzzle)
    row = read_csv_rows(csv_path)[0]
    print(f"category in/out: {tricky_category!r} -> {row['category']!r}")
    print(f"solution in/out: {tricky_solution!r} -> {row['solution']!r}")
    assert row["category"] == tricky_category
    assert row["solution"] == tricky_solution


# --- US2: existing-file load, idempotency, validation (T014) ------------------

def _write_store(csv_path, *puzzles):
    """Write the given puzzles to a fresh CSV store and commit.

    Parameters:
        csv_path: path to write.
        puzzles: the ``Puzzle`` objects to upsert.
    """
    with CsvPuzzleStore(csv_path) as store:
        with store.transaction():
            for p in puzzles:
                store.upsert(p)


def test_reopen_loads_existing_rows(tmp_path):
    """Reopening a CSV written by a prior run loads its rows (keys reconstructed)."""
    csv_path = tmp_path / "out.csv"
    _write_store(csv_path, _sample_puzzle(round="T1"), _sample_puzzle(round="R2"),
                 _sample_puzzle(round="BR"))
    with CsvPuzzleStore(csv_path) as store:
        print(f"loaded count={store.count()}; season 42 count={store.count_for_season(42)}")
        assert store.count() == 3
        assert store.count_for_season(42) == 3


def test_reupsert_existing_key_updates_in_place(tmp_path):
    """Re-upserting an existing key returns 'updated', preserves count, overwrites value."""
    csv_path = tmp_path / "out.csv"
    _write_store(csv_path, _sample_puzzle(round="R2", category="Show Biz"),
                 _sample_puzzle(round="BR", solution="KEEP ME"))
    with CsvPuzzleStore(csv_path) as store:
        with store.transaction():
            result = store.upsert(_sample_puzzle(round="R2", category="Phrase"))
        print(f"reupsert result={result}; count={store.count()}")
        assert result == "updated"
        assert store.count() == 2
    rows = {(r["episode"], r["puzzle_type"], r["puzzle_number"]): r
            for r in read_csv_rows(csv_path)}
    updated = rows[("8011", "Round", "2")]
    print(f"updated row category={updated['category']!r}; rows preserved={len(rows)}")
    assert updated["category"] == "Phrase"           # overwritten in place
    assert ("8011", "Bonus Round", "0") in rows       # other row preserved
    assert len(rows) == 2


def test_header_mismatch_raises_and_leaves_file_untouched(tmp_path):
    """A file whose header doesn't match the canonical header raises DatabaseError (FR-012)."""
    csv_path = tmp_path / "out.csv"
    bad = "episode,season,date,puzzle_type,puzzle_number,category,solution,flags\n"
    csv_path.write_text(bad, encoding="utf-8")
    print(f"pre-existing (wrong) header file contents: {csv_path.read_text()!r}")
    with pytest.raises(DatabaseError):
        CsvPuzzleStore(csv_path)
    assert csv_path.read_text(encoding="utf-8") == bad  # untouched


def test_unreconstructable_existing_row_raises(tmp_path):
    """An existing row whose type/number doesn't reconstruct raises PuzzleParseError (FR-004)."""
    csv_path = tmp_path / "out.csv"
    contents = (
        "season,episode,date,puzzle_type,puzzle_number,category,solution,flags\n"
        "42,8011,2024-09-09,Unknown,3,Show Biz,OPENING NIGHT,[]\n"
    )
    csv_path.write_text(contents, encoding="utf-8")
    print(f"file with unreconstructable row: {contents!r}")
    with pytest.raises(PuzzleParseError):
        CsvPuzzleStore(csv_path)

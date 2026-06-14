"""Unit tests for the SQLite persistence layer (``wheeldb.storage``).

Covers opening/creating the database and schema (foundational), mapping a
``Puzzle`` to a row including the derived columns (US1), and idempotent UPSERT
semantics (US2). Tests run against a throwaway ``tmp_path`` database so nothing
touches a persistent file. Debug output prints the schema and rows at the point
of failure (Constitution Principle V).
"""

from __future__ import annotations

import sqlite3

import pytest

from wheeldb.errors import DatabaseError
from wheeldb.models import Puzzle
from wheeldb.storage import PuzzleStore

#: The columns the puzzles table must expose, in order.
EXPECTED_COLUMNS = [
    "season",
    "episode",
    "round",
    "solution",
    "category",
    "date",
    "puzzle_number",
    "puzzle_type",
    "flags",
]


def _table_info(db_path):
    """Return ``PRAGMA table_info`` rows for the puzzles table.

    Parameters:
        db_path: path to the SQLite database file to inspect.
    Returns:
        The list of ``(cid, name, type, notnull, dflt, pk)`` tuples.
    """
    con = sqlite3.connect(str(db_path))
    try:
        return con.execute("PRAGMA table_info(puzzles)").fetchall()
    finally:
        con.close()


def test_open_creates_database_and_schema(tmp_path):
    """Opening a store creates the file and the puzzles table with the right shape."""
    db_path = tmp_path / "puzzles.sqlite"
    assert not db_path.exists()

    with PuzzleStore(db_path) as store:
        assert store.count() == 0

    info = _table_info(db_path)
    columns = [row[1] for row in info]
    pk_members = [row[1] for row in info if row[5] > 0]
    pk_ordered = [row[1] for row in sorted(info, key=lambda r: r[5]) if row[5] > 0]

    print(f"db exists: {db_path.exists()}")
    print(f"expected columns: {EXPECTED_COLUMNS}")
    print(f"actual columns:   {columns}")
    print(f"primary key members (ordered): {pk_ordered}")

    assert db_path.exists()
    assert columns == EXPECTED_COLUMNS
    assert set(pk_members) == {"season", "episode", "round"}
    assert pk_ordered == ["season", "episode", "round"]


def test_open_is_idempotent(tmp_path):
    """Opening an existing store again does not error or wipe data."""
    db_path = tmp_path / "puzzles.sqlite"
    with PuzzleStore(db_path) as store:
        first = store.count()
    with PuzzleStore(db_path) as store:
        second = store.count()
    print(f"count after first open: {first}; after second open: {second}")
    assert first == 0
    assert second == 0


def test_unopenable_path_raises_database_error(tmp_path):
    """A path that cannot be opened surfaces as DatabaseError, not a raw sqlite error."""
    bad_path = tmp_path / "missing-dir" / "puzzles.sqlite"  # parent does not exist
    print(f"attempting to open: {bad_path}")
    with pytest.raises(DatabaseError):
        PuzzleStore(bad_path)


# --- US1: row mapping (T008) ---------------------------------------------------

def _sample_puzzle(**overrides):
    """Build a Puzzle with sensible defaults for row-mapping tests.

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


def test_upsert_maps_all_attributes_and_derived_columns(tmp_path):
    """A stored row carries the six source attributes plus derived number/type and JSON flags."""
    puzzle = _sample_puzzle(round="R2", flags=(("date", "*"),))
    db_path = tmp_path / "puzzles.sqlite"
    with PuzzleStore(db_path) as store:
        with store.transaction():
            store.upsert(puzzle)
        row = sqlite3.connect(str(db_path)).execute(
            "SELECT season, episode, round, solution, category, date, "
            "puzzle_number, puzzle_type, flags FROM puzzles"
        ).fetchone()

    print(f"source puzzle: {puzzle}")
    print(f"stored row:    {row}")
    print(f"derived number/type expected: {puzzle.puzzle_number}/{puzzle.puzzle_type}")

    assert row == (
        42, 8011, "R2", "OPENING NIGHT", "Show Biz", "2024-09-09",
        2, "Round", '[["date", "*"]]',
    )


def test_upsert_empty_flags_serialize_to_empty_json_array(tmp_path):
    """A puzzle with no flags stores ``[]``."""
    db_path = tmp_path / "puzzles.sqlite"
    with PuzzleStore(db_path) as store:
        with store.transaction():
            store.upsert(_sample_puzzle())
        flags = sqlite3.connect(str(db_path)).execute("SELECT flags FROM puzzles").fetchone()[0]
    print(f"stored flags value: {flags!r}")
    assert flags == "[]"


def test_upsert_unknown_round_raises_and_writes_nothing(tmp_path):
    """A round code with no derivable number raises PuzzleParseError and writes no row."""
    from wheeldb.models import PuzzleParseError

    db_path = tmp_path / "puzzles.sqlite"
    with PuzzleStore(db_path) as store:
        with pytest.raises(PuzzleParseError):
            with store.transaction():
                store.upsert(_sample_puzzle(round="XX"))
        remaining = store.count()
    print(f"rows after failed upsert of unknown round: {remaining}")
    assert remaining == 0


# --- US2: idempotent UPSERT (T015) --------------------------------------------

def test_upsert_is_idempotent_and_reports_added_then_updated(tmp_path):
    """Upserting the same key twice yields one row and reports added then updated."""
    db_path = tmp_path / "puzzles.sqlite"
    with PuzzleStore(db_path) as store:
        with store.transaction():
            first = store.upsert(_sample_puzzle(category="Show Biz"))
        with store.transaction():
            second = store.upsert(_sample_puzzle(category="Phrase"))  # same key, changed attr
        count = store.count()
        stored_category = sqlite3.connect(str(db_path)).execute(
            "SELECT category FROM puzzles"
        ).fetchone()[0]

    print(f"first upsert result: {first}; second: {second}")
    print(f"row count: {count}; stored category: {stored_category}")

    assert first == "added"
    assert second == "updated"
    assert count == 1
    assert stored_category == "Phrase"  # updated in place

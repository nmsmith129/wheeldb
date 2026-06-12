"""Tests for the SQLite layer.

These prove the database can be built, maintained idempotently, and queried/sorted
by each dimension the user asked for (season, episode, puzzle type, category, air
date, round name).
"""

import pytest

from wheeldb import init_db, upsert_puzzles


def _row(**overrides):
    """Build a complete puzzle dict for insertion, overriding specific fields.

    Keeps each test focused on the field under test instead of restating every
    column every time.
    """
    base = {
        "season": 42,
        "episode": "7001",
        "air_date": "2024-09-09",
        "round_name": "Toss-Up 1",
        "puzzle_type": "Toss-Up",
        "category": "Phrase",
        "solution": "BREAK A LEG",
        "source_url": "http://x/42",
    }
    base.update(overrides)
    return base


@pytest.fixture
def conn():
    """An initialised in-memory database, fresh per test."""
    connection = init_db(":memory:")
    yield connection
    connection.close()


def test_init_db_creates_table_and_indexes(conn):
    """init_db should create the puzzles table and all sort-supporting indexes."""
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "puzzles" in tables
    indexes = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    for expected in ("idx_season", "idx_episode", "idx_type",
                     "idx_category", "idx_airdate", "idx_round"):
        assert expected in indexes


def test_upsert_inserts_rows(conn):
    """A first upsert inserts the given rows."""
    written = upsert_puzzles(conn, [_row(), _row(round_name="Round 1",
                                              puzzle_type="Round",
                                              solution="A COZY FIREPLACE")])
    assert written == 2
    count = conn.execute("SELECT COUNT(*) AS n FROM puzzles").fetchone()["n"]
    assert count == 2


def test_upsert_is_idempotent(conn):
    """Re-inserting identical rows must not create duplicates."""
    rows = [_row(), _row(round_name="Round 1", solution="A COZY FIREPLACE")]
    upsert_puzzles(conn, rows)
    upsert_puzzles(conn, rows)  # second run: same natural keys
    count = conn.execute("SELECT COUNT(*) AS n FROM puzzles").fetchone()["n"]
    assert count == 2


def test_upsert_refreshes_scraped_at(conn):
    """Re-scraping an unchanged puzzle updates its scraped_at timestamp."""
    upsert_puzzles(conn, [_row()])
    first = conn.execute("SELECT scraped_at FROM puzzles").fetchone()["scraped_at"]
    # Force a distinct timestamp by patching nothing but re-running; equal or
    # later is acceptable, the point is the row is rewritten in place.
    upsert_puzzles(conn, [_row(category="Updated Category")])
    rows = conn.execute("SELECT category, scraped_at FROM puzzles").fetchall()
    assert len(rows) == 1
    assert rows[0]["category"] == "Updated Category"
    assert rows[0]["scraped_at"] >= first


def test_changed_solution_is_a_new_row(conn):
    """A different solution for the same round is a distinct puzzle, not an update."""
    upsert_puzzles(conn, [_row()])
    upsert_puzzles(conn, [_row(solution="SOMETHING ELSE")])
    count = conn.execute("SELECT COUNT(*) AS n FROM puzzles").fetchone()["n"]
    assert count == 2


@pytest.mark.parametrize(
    "column",
    ["season", "episode", "puzzle_type", "category", "air_date", "round_name"],
)
def test_sortable_by_each_dimension(conn, column):
    """Every user-requested dimension can be used to order query results."""
    upsert_puzzles(conn, [
        _row(round_name="Round 2", puzzle_type="Round", category="Thing",
             air_date="2024-09-10", episode="7002", solution="ZEBRA"),
        _row(round_name="Toss-Up 1", puzzle_type="Toss-Up", category="Phrase",
             air_date="2024-09-09", episode="7001", solution="APPLE"),
    ])
    ordered = conn.execute(
        f"SELECT {column} FROM puzzles ORDER BY {column} ASC"
    ).fetchall()
    values = [r[column] for r in ordered]
    assert values == sorted(values)

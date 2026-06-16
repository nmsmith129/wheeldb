"""SQLite persistence for parsed puzzles.

The single module that knows the database schema and SQL. It maps ``Puzzle``
value objects to rows of a one-table SQLite database, idempotently, keyed on the
stable identity ``(season, episode, round)``. Usable without the CLI and without
network access (Constitution Principle I); the schema is created on first open so
no manual setup is needed (FR-005).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager

from wheeldb.errors import DatabaseError
from wheeldb.models import Puzzle

#: DDL for the one puzzle table. Column order matches data-model.md; the stable
#: key is the composite primary key (season, episode, round).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS puzzles (
    season        INTEGER NOT NULL,
    episode       INTEGER NOT NULL,
    round         TEXT    NOT NULL,
    solution      TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    date          TEXT    NOT NULL,
    puzzle_number INTEGER NOT NULL,
    puzzle_type   TEXT    NOT NULL,
    flags         TEXT    NOT NULL DEFAULT '[]',
    PRIMARY KEY (season, episode, round)
);
"""


class PuzzleStore:
    """A SQLite-backed store of puzzle rows.

    Opening a store creates the database file (and the ``puzzles`` table) when
    absent. Writes happen inside a ``transaction()`` so a unit of work commits or
    rolls back as a whole.
    """

    def __init__(self, path):
        """Open (creating if absent) the database at ``path`` and ensure the schema.

        Parameters:
            path: filesystem path to the SQLite database file.
        Raises:
            DatabaseError: the database could not be opened or the schema created.
        """
        self._path = os.fspath(path)
        try:
            self._con = sqlite3.connect(self._path)
            self._con.executescript(_SCHEMA)
            self._con.commit()
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not open puzzle database at {self._path}: {exc}") from exc

    def __enter__(self) -> "PuzzleStore":
        """Enter a ``with`` block, returning this store."""
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        """Close the connection on leaving a ``with`` block.

        Parameters:
            exc_type, exc, tb: the active exception, if any (not suppressed).
        Returns:
            ``False`` so any exception propagates.
        """
        self.close()
        return False

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._con.close()

    @contextmanager
    def transaction(self):
        """Run a unit of work that commits on success and rolls back on error.

        Yields:
            This store, so writes can be issued inside the ``with`` block. On a
            clean exit the work is committed; on any exception it is rolled back
            and the exception re-raised.
        """
        try:
            yield self
        except BaseException:
            self.rollback()
            raise
        else:
            self.commit()

    def commit(self) -> None:
        """Commit the current transaction."""
        self._con.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self._con.rollback()

    def upsert(self, puzzle: Puzzle) -> str:
        """Write one puzzle as a row, returning whether it was added or updated.

        The derived ``puzzle_number``/``puzzle_type`` are read from the puzzle and
        ``flags`` is JSON-encoded. ``puzzle_number`` is read *before* any write so
        a ``PuzzleParseError`` (unrecognized round code) propagates without
        touching the database (FR-010).

        Parameters:
            puzzle: the ``Puzzle`` to persist.
        Returns:
            ``"added"`` if no row existed for ``(season, episode, round)``, else
            ``"updated"`` (the existing row is overwritten in place).
        Raises:
            PuzzleParseError: the round code yields no derivable puzzle number.
            DatabaseError: an underlying SQLite error occurred during the write.
        """
        number = puzzle.puzzle_number  # may raise PuzzleParseError (FR-010)
        ptype = puzzle.puzzle_type
        flags = json.dumps([list(pair) for pair in puzzle.flags])
        key = (puzzle.season, puzzle.episode, puzzle.round)
        try:
            existed = self._con.execute(
                "SELECT 1 FROM puzzles WHERE season = ? AND episode = ? AND round = ?",
                key,
            ).fetchone() is not None
            self._con.execute(
                "INSERT INTO puzzles "
                "(season, episode, round, solution, category, date, "
                " puzzle_number, puzzle_type, flags) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(season, episode, round) DO UPDATE SET "
                " solution=excluded.solution, category=excluded.category, "
                " date=excluded.date, puzzle_number=excluded.puzzle_number, "
                " puzzle_type=excluded.puzzle_type, flags=excluded.flags",
                (*key, puzzle.solution, puzzle.category, puzzle.date, number, ptype, flags),
            )
        except sqlite3.Error as exc:
            raise DatabaseError(f"failed writing puzzle {key}: {exc}") from exc
        return "updated" if existed else "added"

    def puzzles_for_season(self, season: int) -> list[Puzzle]:
        """Return one season's stored puzzles as ``Puzzle`` objects.

        Reuses the same column set the store persists, reconstructing each
        ``Puzzle`` from its row so callers (e.g. game generation) can group by the
        model's derived ``puzzle_type`` without a parallel data path (Principle IV).
        The ``round`` column is read directly, so the derived type/number come from
        the model rather than the stored copies.

        Parameters:
            season: the season number to read puzzles for.
        Returns:
            A list of ``Puzzle`` objects for ``season`` (empty if the season is
            absent), in the database's natural row order.
        Raises:
            DatabaseError: an underlying SQLite error occurred during the read.
        """
        try:
            rows = self._con.execute(
                "SELECT solution, category, date, season, episode, round, flags "
                "FROM puzzles WHERE season = ?",
                (season,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(
                f"failed reading puzzles for season {season}: {exc}"
            ) from exc
        puzzles = []
        for solution, category, date, season_no, episode, round_code, flags in rows:
            flag_pairs = tuple(tuple(pair) for pair in json.loads(flags))
            puzzles.append(
                Puzzle(
                    solution=solution,
                    category=category,
                    date=date,
                    season=season_no,
                    episode=episode,
                    round=round_code,
                    flags=flag_pairs,
                )
            )
        return puzzles

    def count(self) -> int:
        """Return the total number of stored puzzle rows.

        Returns:
            The row count of the ``puzzles`` table.
        """
        return self._con.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]

    def count_for_season(self, season: int) -> int:
        """Return the number of stored rows for one season.

        Parameters:
            season: the season number to count rows for.
        Returns:
            The number of ``puzzles`` rows whose ``season`` equals ``season``.
        """
        return self._con.execute(
            "SELECT COUNT(*) FROM puzzles WHERE season = ?", (season,)
        ).fetchone()[0]

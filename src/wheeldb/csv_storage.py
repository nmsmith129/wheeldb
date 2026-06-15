"""CSV persistence for parsed puzzles.

A drop-in alternative to :class:`wheeldb.storage.PuzzleStore` that serializes
puzzles to a plain-text CSV file instead of SQLite, mirroring the same interface
(context manager, ``transaction()``, ``upsert()`` returning ``"added"``/
``"updated"``, ``count()``, ``count_for_season()``) so ``ingest_seasons`` drives
either store unchanged (Constitution Principle IV). Usable without the CLI and
without network access (Principle I).

The store keeps an insertion-ordered working set keyed on the stable identity
``(season, episode, round)`` — the same key the SQLite store uses. A CSV row has
no ``round`` column, so on read the round code is reconstructed from the
``puzzle_type``/``puzzle_number`` columns. Each transaction reads-merges-rewrites
the whole file with an atomic temp-file replace, giving all-or-nothing-per-season
semantics (FR-009).
"""

from __future__ import annotations

import csv
import json
import os
from contextlib import contextmanager

from wheeldb.errors import DatabaseError
from wheeldb.models import Puzzle, round_from_type_and_number

#: The canonical CSV columns, in order (FR-003). The first seven are the
#: user-requested fields; ``flags`` is the trailing JSON-encoded cell (FR-006).
HEADER = [
    "season",
    "episode",
    "date",
    "puzzle_type",
    "puzzle_number",
    "category",
    "solution",
    "flags",
]


class CsvPuzzleStore:
    """A CSV-backed store of puzzle rows mirroring ``PuzzleStore``.

    Opening a store loads any existing rows into an in-memory ordered dict keyed
    on ``(season, episode, round)``. Writes happen inside a ``transaction()`` so a
    unit of work commits (atomically rewriting the file) or rolls back as a whole.
    """

    def __init__(self, path):
        """Open the CSV store at ``path``, loading existing rows if the file exists.

        Parameters:
            path: filesystem path to the CSV file (created on first commit).
        Raises:
            DatabaseError: the file exists with a header that does not exactly
                match the canonical header (FR-012).
            PuzzleParseError: an existing row's puzzle_type/puzzle_number does not
                reconstruct to a recognized round code (FR-004).
        """
        self._path = os.fspath(path)
        self._rows: dict[tuple[int, int, str], list[str]] = {}
        self._snapshot: dict[tuple[int, int, str], list[str]] | None = None
        self._load_existing()

    def _load_existing(self) -> None:
        """Load rows from an existing file into the working set (merge target).

        Reads the file (if present and non-empty), validates its header exactly
        matches the canonical header, and reconstructs each row's
        ``(season, episode, round)`` key from the ``puzzle_type``/``puzzle_number``
        columns so a re-ingest de-duplicates and updates in place (FR-004).

        Raises:
            DatabaseError: the file exists with a header that does not exactly
                match the canonical header (FR-012), or could not be read.
            PuzzleParseError: an existing row's puzzle_type/puzzle_number does not
                reconstruct to a recognized round code (FR-004).
        """
        if not os.path.exists(self._path) or os.path.getsize(self._path) == 0:
            return
        try:
            with open(self._path, newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                rows = list(reader)
        except OSError as exc:
            raise DatabaseError(f"could not read CSV file at {self._path}: {exc}") from exc
        if not rows:
            return
        header, data = rows[0], rows[1:]
        if header != HEADER:
            raise DatabaseError(
                f"CSV header mismatch in {self._path}: expected {HEADER}, got {header}"
            )
        for row in data:
            season, episode = int(row[0]), int(row[1])
            ptype, number = row[3], int(row[4])
            round_code = round_from_type_and_number(ptype, number)
            self._rows[(season, episode, round_code)] = row

    def __enter__(self) -> "CsvPuzzleStore":
        """Enter a ``with`` block, returning this store."""
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        """Leave a ``with`` block (no resource to close beyond the in-memory dict).

        Parameters:
            exc_type, exc, tb: the active exception, if any (not suppressed).
        Returns:
            ``False`` so any exception propagates.
        """
        return False

    @contextmanager
    def transaction(self):
        """Run a unit of work that commits on success and rolls back on error.

        Yields:
            This store, so writes can be issued inside the ``with`` block. The
            in-memory dict is snapshotted on entry; on a clean exit the work is
            committed (the file is rewritten atomically), on any exception it is
            rolled back and the exception re-raised.
        """
        self._snapshot = dict(self._rows)
        try:
            yield self
        except BaseException:
            self.rollback()
            raise
        else:
            self.commit()

    def commit(self) -> None:
        """Atomically rewrite the whole file from the in-memory rows.

        Writes the header plus every staged row (in insertion order) to a sibling
        temp file, then ``os.replace`` it into place so the target file is either
        fully updated or left untouched (FR-009).

        Raises:
            DatabaseError: the file could not be written or replaced.
        """
        tmp_path = f"{self._path}.tmp"
        try:
            with open(tmp_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(HEADER)
                for row in self._rows.values():
                    writer.writerow(row)
            os.replace(tmp_path, self._path)
        except OSError as exc:
            raise DatabaseError(f"could not write CSV file at {self._path}: {exc}") from exc
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        self._snapshot = None

    def rollback(self) -> None:
        """Restore the in-memory rows from the transaction snapshot.

        The on-disk file is not touched (no commit happened).
        """
        if self._snapshot is not None:
            self._rows = self._snapshot
            self._snapshot = None

    def upsert(self, puzzle: Puzzle) -> str:
        """Stage one puzzle as a row, returning whether it was added or updated.

        ``puzzle_number`` is read *before* any mutation so a ``PuzzleParseError``
        (unrecognized round code) propagates without changing the store (FR-010).

        Parameters:
            puzzle: the ``Puzzle`` to persist.
        Returns:
            ``"added"`` if no row existed for ``(season, episode, round)``, else
            ``"updated"`` (the existing row is overwritten in place, last wins).
        """
        number = puzzle.puzzle_number  # may raise PuzzleParseError (FR-010)
        ptype = puzzle.puzzle_type
        flags = json.dumps([list(pair) for pair in puzzle.flags])
        key = (puzzle.season, puzzle.episode, puzzle.round)
        row = [
            str(puzzle.season),
            str(puzzle.episode),
            puzzle.date,
            ptype,
            str(number),
            puzzle.category,
            puzzle.solution,
            flags,
        ]
        existed = key in self._rows
        self._rows[key] = row
        return "updated" if existed else "added"

    def count(self) -> int:
        """Return the total number of staged puzzle rows.

        Returns:
            The number of rows in the in-memory working set.
        """
        return len(self._rows)

    def count_for_season(self, season: int) -> int:
        """Return the number of staged rows for one season.

        Parameters:
            season: the season number to count rows for.
        Returns:
            The number of rows whose ``season`` equals ``season``.
        """
        return sum(1 for (s, _e, _r) in self._rows if s == season)

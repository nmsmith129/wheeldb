"""Season-ingest orchestration.

Parses the ingest argument (a single season or an inclusive range) and drives the
existing fetch + parser layers to write a season's puzzles into a ``PuzzleStore``.
Ingestion is confined to exactly the requested season(s) (FR-008a) and is
best-effort per season: each season commits on its own, an unretrievable season
is reported and skipped, and a data error halts the run (see ``ingest_seasons``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from wheeldb.csv_storage import CsvPuzzleStore
from wheeldb.errors import ParseError, RetrievalError
from wheeldb.fetch import HttpFetcher
from wheeldb.parser import find_puzzle_table, parse_rows
from wheeldb.storage import PuzzleStore

#: A single season number, e.g. ``40``.
_SEASON_RE = re.compile(r"^\d+$")

#: An inclusive ``start-end`` range, e.g. ``37-40``.
_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")


@dataclass
class IngestSummary:
    """The outcome of an ingest run (no puzzle text — spoiler-free, FR-009).

    Attributes:
        seasons: season numbers committed, in order.
        skipped: requested seasons skipped because their page could not be
            retrieved (best-effort).
        unparsed: requested seasons whose page was retrieved but contained no
            recognizable puzzle table (distinct from a retrieval failure).
        added: rows newly inserted across committed seasons.
        updated: existing rows updated in place across committed seasons.
    """

    seasons: list[int] = field(default_factory=list)
    skipped: list[int] = field(default_factory=list)
    unparsed: list[int] = field(default_factory=list)
    added: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        """Return the number of puzzles written (``added + updated``)."""
        return self.added + self.updated


def parse_season_arg(text: str) -> list[int]:
    """Parse the ingest argument into the ascending list of seasons to process.

    Parameters:
        text: the raw argument — a single season (``"40"``) or an inclusive
            ascending range (``"37-40"``). Equal endpoints (``"40-40"``) mean the
            single season.
    Returns:
        The explicit list of season numbers, ascending. This is the complete set
        of seasons that may be fetched (FR-008a).
    Raises:
        ValueError: the argument is empty, malformed, or a reversed range
            (start greater than end).
    """
    value = text.strip()

    if _SEASON_RE.match(value):
        return [int(value)]

    match = _RANGE_RE.match(value)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        if start > end:
            raise ValueError(
                f"invalid season range {value!r}: start {start} is greater than end {end}"
            )
        return list(range(start, end + 1))

    raise ValueError(
        f"invalid season argument {text!r}: expected a season (e.g. '40') "
        "or an inclusive range (e.g. '37-40')"
    )


def ingest_seasons(season_arg, *, db_path, fetcher=None, store_format="sqlite") -> IngestSummary:
    """Ingest every puzzle of the requested season(s) into the chosen store.

    Reuses the existing fetch + parser layers (FR-001) and confines retrieval to
    exactly the requested seasons (FR-008a). Best-effort per season (Decision 5):
    each season commits in its own transaction; an unretrievable season is
    reported in ``skipped`` and a retrieved-but-table-less season in ``unparsed``
    (the loop continues for both); a data error (``PuzzleParseError``) or a
    ``DatabaseError`` rolls back that season and halts the run by propagating,
    leaving earlier seasons committed (FR-010/011). A within-run duplicate stable
    key collapses to one row and is counted once.

    Parameters:
        season_arg: a raw argument string (``"40"`` / ``"37-40"``) parsed via
            :func:`parse_season_arg`, or an already-resolved iterable of season
            ints.
        db_path: filesystem path to the output file (created if absent). For the
            SQLite format this is the database path; for CSV it is the ``.csv``
            file path (derived by the CLI per FR-002a).
        fetcher: a ``Fetcher`` supplying season HTML; defaults to a live
            ``HttpFetcher``. Tests inject a fixture-backed fetcher.
        store_format: ``"sqlite"`` (default — unchanged behavior, FR-002) selects
            :class:`~wheeldb.storage.PuzzleStore`; ``"csv"`` selects
            :class:`~wheeldb.csv_storage.CsvPuzzleStore`. The season loop and all
            best-effort/counting behavior are identical for either store.
    Returns:
        An :class:`IngestSummary` of committed seasons, skipped seasons, and
        added/updated counts.
    Raises:
        PuzzleParseError: a round code yielded no puzzle number (halts the run).
        DatabaseError: a SQLite error occurred (halts the run).
    """
    if isinstance(season_arg, str):
        seasons = parse_season_arg(season_arg)
    else:
        seasons = sorted({int(s) for s in season_arg})

    if fetcher is None:
        fetcher = HttpFetcher()

    summary = IngestSummary()
    seen_keys: set[tuple[int, int, str]] = set()
    store_factory = CsvPuzzleStore if store_format == "csv" else PuzzleStore
    with store_factory(db_path) as store:
        for season in seasons:
            try:
                html = fetcher.get_season_html(season)
            except RetrievalError:
                summary.skipped.append(season)  # best-effort: skip and continue
                continue
            try:
                with store.transaction():
                    table = find_puzzle_table(html)
                    for puzzle in parse_rows(table, season):
                        result = store.upsert(puzzle)
                        key = (puzzle.season, puzzle.episode, puzzle.round)
                        if key in seen_keys:
                            # within-run duplicate stable key: the row was already
                            # counted; this upsert just overwrites it (last wins),
                            # so it must not inflate added/updated/total.
                            continue
                        seen_keys.add(key)
                        if result == "added":
                            summary.added += 1
                        else:
                            summary.updated += 1
            except ParseError:
                summary.unparsed.append(season)  # retrieved but no puzzle table
                continue
            summary.seasons.append(season)
    return summary

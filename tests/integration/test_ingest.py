"""Integration tests for season ingestion (``wheeldb.ingest`` + ``wheeldb.cli``).

Exercises the end-to-end path fetch -> parse -> store over saved season fixtures
into a throwaway ``tmp_path`` database. Covers single-season ingest and atomic
abort (US1), idempotent + additive re-ingestion (US2), and range ingest with
bounded fetch and best-effort skip (US3). Debug output prints seasons,
committed/skipped, and counts at the point of failure (Principle V).
"""

from __future__ import annotations

import sqlite3

import pytest
from conftest import FixtureFetcher, RecordingFetcher

from wheeldb import cli
from wheeldb.ingest import ingest_seasons
from wheeldb.models import Puzzle, PuzzleParseError
from wheeldb.parser import find_puzzle_table, parse_rows
from wheeldb.storage import PuzzleStore

#: Aliases three arbitrary season numbers to the three real fixtures, so a
#: contiguous range can be exercised offline.
_RANGE_FILES = {37: "compendium1.html", 38: "compendium20.html", 39: "compendium42.html"}


def _expected_puzzles(season: int, *, file: str | None = None):
    """Parse a fixture season the same way ingestion does, for expected values.

    Parameters:
        season: the season number to stamp on the parsed puzzles.
        file: optional fixture filename override (defaults to compendium{season}).
    Returns:
        The list of ``Puzzle`` objects the parser produces for that fixture.
    """
    fetcher = RecordingFetcher(files={season: file}) if file else FixtureFetcher([season])
    html = fetcher.get_season_html(season)
    return parse_rows(find_puzzle_table(html), season)


# --- US1: single-season ingest -------------------------------------------------

def test_ingest_single_season_stores_one_row_per_puzzle(tmp_path):
    """Ingesting a season writes exactly one row per parsed puzzle, all in that season."""
    db_path = tmp_path / "puzzles.sqlite"
    expected = _expected_puzzles(42)

    summary = ingest_seasons("42", db_path=db_path, fetcher=FixtureFetcher([42]))

    con = sqlite3.connect(str(db_path))
    total = con.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    seasons_in_db = {r[0] for r in con.execute("SELECT DISTINCT season FROM puzzles")}

    print(f"parsed {len(expected)} puzzles; stored {total} rows; summary={summary}")
    assert total == len(expected)
    assert summary.total == len(expected)
    assert summary.seasons == [42]
    assert summary.skipped == []
    assert seasons_in_db == {42}


def test_ingest_single_season_row_values_match_parser(tmp_path):
    """A stored row's attributes and derived columns match what the parser produced."""
    db_path = tmp_path / "puzzles.sqlite"
    expected = _expected_puzzles(42)
    first = expected[0]

    ingest_seasons("42", db_path=db_path, fetcher=FixtureFetcher([42]))

    row = sqlite3.connect(str(db_path)).execute(
        "SELECT solution, category, date, season, episode, round, puzzle_number, puzzle_type "
        "FROM puzzles WHERE episode = ? AND round = ?",
        (first.episode, first.round),
    ).fetchone()
    print(f"expected first puzzle: {first}")
    print(f"stored row: {row}")
    assert row == (
        first.solution, first.category, first.date, first.season, first.episode,
        first.round, first.puzzle_number, first.puzzle_type,
    )


def test_ingest_data_error_aborts_season_and_writes_nothing(tmp_path):
    """A round code with no derivable number raises and leaves the season's rows unwritten."""
    db_path = tmp_path / "puzzles.sqlite"
    fetcher = RecordingFetcher(files={66: "compendium_badround.html"})

    with pytest.raises(PuzzleParseError):
        ingest_seasons("66", db_path=db_path, fetcher=fetcher)

    total = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    print(f"rows after data-error abort: {total} (expected 0)")
    assert total == 0


def test_ingest_single_season_retrieval_failure_skips_without_raising(tmp_path):
    """A single unretrievable season returns a summary listing it skipped; DB unchanged."""
    db_path = tmp_path / "puzzles.sqlite"
    # FixtureFetcher serves only 1/20/42; season 99 raises RetrievalError.
    summary = ingest_seasons("99", db_path=db_path, fetcher=FixtureFetcher([1, 20, 42]))

    total = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    print(f"summary={summary}; rows={total}")
    assert summary.seasons == []
    assert summary.skipped == [99]
    assert summary.total == 0
    assert total == 0


# --- US1: CLI ------------------------------------------------------------------

def test_cli_ingest_reports_counts_and_provenance_without_spoilers(tmp_path, capsys):
    """`wheeldb ingest <season>` prints counts/season/source and never a solution."""
    db_path = tmp_path / "puzzles.sqlite"
    expected = _expected_puzzles(42)

    code = cli.main(["ingest", "42", "--db", str(db_path)], fetcher=FixtureFetcher([42]))
    out = capsys.readouterr().out

    print(f"exit={code}\nstdout:\n{out}")
    assert code == 0
    assert "42" in out                       # season reported
    assert "compendium42" in out             # provenance/source URL
    assert str(len(expected)) in out         # count reported
    # spoiler-free: no solution text appears on stdout
    for puzzle in expected:
        assert puzzle.solution not in out


def test_cli_ingest_rejects_malformed_argument(tmp_path, capsys):
    """A malformed season argument exits non-zero, prints usage, and writes nothing."""
    db_path = tmp_path / "puzzles.sqlite"
    code = cli.main(["ingest", "abc", "--db", str(db_path)], fetcher=FixtureFetcher([42]))
    err = capsys.readouterr().err

    print(f"exit={code}\nstderr:\n{err}")
    assert code != 0
    assert not db_path.exists() or sqlite3.connect(str(db_path)).execute(
        "SELECT COUNT(*) FROM puzzles"
    ).fetchone()[0] == 0


# --- US2: idempotent + additive re-ingestion -----------------------------------

def test_reingesting_same_season_is_idempotent(tmp_path):
    """Re-ingesting a season leaves the row count unchanged; the rerun reports updates."""
    db_path = tmp_path / "puzzles.sqlite"
    first = ingest_seasons("42", db_path=db_path, fetcher=FixtureFetcher([42]))
    second = ingest_seasons("42", db_path=db_path, fetcher=FixtureFetcher([42]))

    total = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    print(f"first={first}; second={second}; rows={total}")
    assert total == first.total
    assert second.added == 0
    assert second.updated == second.total == first.total


def test_reingestion_is_additive_and_never_prunes(tmp_path):
    """A pre-existing row absent from the new parse survives re-ingestion (FR-007a)."""
    db_path = tmp_path / "puzzles.sqlite"
    extra = Puzzle(
        solution="LEFTOVER", category="Phrase", date="2024-01-01",
        season=42, episode=9999, round="R9", flags=(),
    )
    with PuzzleStore(db_path) as store:
        with store.transaction():
            store.upsert(extra)

    ingest_seasons("42", db_path=db_path, fetcher=FixtureFetcher([42]))

    survived = sqlite3.connect(str(db_path)).execute(
        "SELECT COUNT(*) FROM puzzles WHERE season=42 AND episode=9999 AND round='R9'"
    ).fetchone()[0]
    print(f"pre-seeded extra row still present: {survived} (expected 1)")
    assert survived == 1


# --- US3: range ingest, bounded fetch, best-effort skip ------------------------

def test_ingest_range_stores_each_season_and_stays_bounded(tmp_path):
    """A range ingests every in-range season and fetches only those seasons."""
    db_path = tmp_path / "puzzles.sqlite"
    fetcher = RecordingFetcher(available=(), files=_RANGE_FILES)

    summary = ingest_seasons("37-39", db_path=db_path, fetcher=fetcher)

    con = sqlite3.connect(str(db_path))
    per_season = {
        s: con.execute("SELECT COUNT(*) FROM puzzles WHERE season=?", (s,)).fetchone()[0]
        for s in (37, 38, 39)
    }
    print(f"requested={fetcher.requested}; per-season rows={per_season}; summary={summary}")
    assert fetcher.requested == [37, 38, 39]
    assert summary.seasons == [37, 38, 39]
    assert summary.skipped == []
    assert all(count > 0 for count in per_season.values())


def test_ingest_range_skips_unretrievable_season_best_effort(tmp_path):
    """One unretrievable season is skipped; the others still commit (FR-011/SC-009)."""
    db_path = tmp_path / "puzzles.sqlite"
    # 38 is absent -> RetrievalError -> skipped; 37/39/40 are served.
    files = {37: "compendium1.html", 39: "compendium20.html", 40: "compendium42.html"}
    fetcher = RecordingFetcher(available=(), files=files)

    summary = ingest_seasons("37-40", db_path=db_path, fetcher=fetcher)

    con = sqlite3.connect(str(db_path))
    seasons_in_db = sorted({r[0] for r in con.execute("SELECT DISTINCT season FROM puzzles")})
    print(f"requested={fetcher.requested}; committed={summary.seasons}; "
          f"skipped={summary.skipped}; db seasons={seasons_in_db}")
    assert fetcher.requested == [37, 38, 39, 40]
    assert summary.seasons == [37, 39, 40]
    assert summary.skipped == [38]
    assert seasons_in_db == [37, 39, 40]


def test_cli_ingest_range_lists_sources_without_spoilers(tmp_path, capsys):
    """`wheeldb ingest <range>` lists each committed season's source URL, no solutions."""
    db_path = tmp_path / "puzzles.sqlite"
    fetcher = RecordingFetcher(available=(), files=_RANGE_FILES)

    code = cli.main(["ingest", "37-39", "--db", str(db_path)], fetcher=fetcher)
    out = capsys.readouterr().out
    print(f"exit={code}\nstdout:\n{out}")

    assert code == 0
    for season in (37, 38, 39):
        assert f"compendium{season}" in out
    # spoiler-free across all committed seasons
    expected = []
    for season, file in _RANGE_FILES.items():
        expected += _expected_puzzles(season, file=file)
    for puzzle in expected:
        assert puzzle.solution not in out


def test_cli_ingest_range_reports_skipped_season_and_exits_nonzero(tmp_path, capsys):
    """When a season is skipped, the CLI names it on stdout and exits non-zero."""
    db_path = tmp_path / "puzzles.sqlite"
    files = {37: "compendium1.html", 39: "compendium20.html", 40: "compendium42.html"}
    fetcher = RecordingFetcher(available=(), files=files)

    code = cli.main(["ingest", "37-40", "--db", str(db_path)], fetcher=fetcher)
    out = capsys.readouterr().out
    print(f"exit={code}\nstdout:\n{out}")

    assert code != 0
    assert "38" in out
    assert "kip" in out  # "Skipped"/"skipped"


# --- Code-review fix #1: within-season duplicate key counts once ---------------

def test_ingest_within_season_duplicate_key_counts_rows_written(tmp_path):
    """Two parsed puzzles sharing a key collapse to one row, and total reflects that."""
    db_path = tmp_path / "puzzles.sqlite"
    fetcher = RecordingFetcher(files={70: "compendium_dupround.html"})

    summary = ingest_seasons("70", db_path=db_path, fetcher=fetcher)

    rows = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    print(f"rows={rows}; summary={summary}")
    assert rows == 1                       # duplicate (season,episode,round) collapses
    assert summary.total == rows           # count must match rows written
    assert summary.added == 1
    assert summary.updated == 0


# --- Code-review fix #2: parse failure reported distinctly from retrieval -------

def test_ingest_unparsed_season_reported_separately_from_skipped(tmp_path):
    """A retrieved-but-untable-less page lands in `unparsed`, not `skipped`."""
    db_path = tmp_path / "puzzles.sqlite"
    fetcher = RecordingFetcher(files={71: "compendium_notable.html"})

    summary = ingest_seasons("71", db_path=db_path, fetcher=fetcher)

    print(f"summary={summary}")
    assert summary.seasons == []
    assert summary.skipped == []           # it WAS retrieved
    assert summary.unparsed == [71]


def test_cli_unparsed_season_not_mislabeled_as_retrieval_failure(tmp_path, capsys):
    """The CLI must not claim 'could not retrieve' for a page that parsed empty."""
    db_path = tmp_path / "puzzles.sqlite"
    fetcher = RecordingFetcher(files={71: "compendium_notable.html"})

    code = cli.main(["ingest", "71", "--db", str(db_path)], fetcher=fetcher)
    out = capsys.readouterr().out
    print(f"exit={code}\nstdout:\n{out}")

    assert code != 0
    assert "71" in out
    assert "could not retrieve" not in out

"""Spoiler-free command-line interface.

Per Constitution Principle II, the CLI reports counts and provenance to stdout
and diagnostics/errors to stderr, and never prints puzzle solutions. Puzzle text
surfaces only behind the test boundary.
"""

from __future__ import annotations

import argparse
import sys

from wheeldb.episodes import extract_episode
from wheeldb.errors import DatabaseError, RetrievalError
from wheeldb.fetch import season_url
from wheeldb.ingest import ingest_seasons, parse_season_arg
from wheeldb.models import PuzzleParseError


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``wheeldb`` command.

    Returns:
        An ``ArgumentParser`` with an ``episode <number>`` subcommand.
    """
    parser = argparse.ArgumentParser(
        prog="wheeldb",
        description="Report the puzzles that aired in a Wheel of Fortune episode "
        "(without revealing the solutions).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    episode = sub.add_parser("episode", help="Look up puzzles by episode number.")
    episode.add_argument("number", type=int, help="Global episode number, e.g. 8011.")

    ingest = sub.add_parser(
        "ingest",
        help="Store a season's (or a season range's) puzzles in the SQLite database.",
    )
    ingest.add_argument(
        "seasons",
        help="A single season (e.g. 40) or an inclusive range (e.g. 37-40).",
    )
    ingest.add_argument(
        "--db",
        default="wheeldb.sqlite",
        help="SQLite database file to write (default: wheeldb.sqlite in the CWD).",
    )
    return parser


def main(argv=None, *, fetcher=None) -> int:
    """Run the CLI.

    Parameters:
        argv: argument list (defaults to ``sys.argv[1:]``).
        fetcher: optional ``Fetcher`` injected for offline testing; defaults to
            the live HTTP fetcher.
    Returns:
        Process exit code: 0 on success (including zero puzzles found), 2 on a
        retrieval failure.
    """
    args = _build_parser().parse_args(argv)

    if args.command == "ingest":
        return _run_ingest(args, fetcher)

    try:
        puzzles = extract_episode(args.number, fetcher=fetcher)
    except RetrievalError as exc:
        print(f"error: could not retrieve season data: {exc}", file=sys.stderr)
        return 2

    if not puzzles:
        print(f"Episode {args.number}: 0 puzzles found")
        return 0

    season = puzzles[0].season
    rounds = ", ".join(p.round for p in puzzles)
    print(f"Episode {args.number} (Season {season}): {len(puzzles)} puzzles found")
    print(f"  Rounds: {rounds}")
    print(f"  Source: {season_url(season)}")
    return 0


def _run_ingest(args, fetcher) -> int:
    """Execute the ``ingest`` subcommand, printing a spoiler-free summary.

    Parameters:
        args: parsed arguments carrying ``seasons`` (the raw season/range string)
            and ``db`` (the database path).
        fetcher: optional ``Fetcher`` injected for offline testing.
    Returns:
        Exit code: 0 on a fully clean run; 2 on a bad argument, a skipped season,
        or a halting data/database error.
    """
    try:
        seasons = parse_season_arg(args.seasons)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("usage: wheeldb ingest <season|range> [--db PATH]", file=sys.stderr)
        return 2

    try:
        summary = ingest_seasons(seasons, db_path=args.db, fetcher=fetcher)
    except PuzzleParseError as exc:
        print(f"error: cannot derive puzzle number: {exc}", file=sys.stderr)
        return 2
    except DatabaseError as exc:
        print(f"error: database error: {exc}", file=sys.stderr)
        return 2

    _print_ingest_summary(summary, args.db)
    return 2 if (summary.skipped or summary.unparsed) else 0


def _print_ingest_summary(summary, db_path) -> None:
    """Print a spoiler-free ingest summary to stdout (counts, seasons, provenance).

    Parameters:
        summary: the ``IngestSummary`` returned by ``ingest_seasons``.
        db_path: the database path that was written (for the report header).
    """
    seasons = summary.seasons
    if not seasons:
        header = "no seasons"
    elif len(seasons) == 1:
        header = f"season {seasons[0]}"
    else:
        header = f"seasons {', '.join(str(s) for s in seasons)}"
    not_committed = len(summary.skipped) + len(summary.unparsed)
    suffix = f" ({not_committed} season(s) not ingested)" if not_committed else ""
    print(f"Ingested {header} into {db_path}{suffix}")
    print(
        f"  Puzzles: {summary.added} added, {summary.updated} updated "
        f"({summary.total} total)"
    )
    if summary.skipped:
        skipped = ", ".join(str(s) for s in summary.skipped)
        print(f"  Skipped: season(s) {skipped} (could not retrieve source)")
    if summary.unparsed:
        unparsed = ", ".join(str(s) for s in summary.unparsed)
        print(f"  No puzzle table: season(s) {unparsed} (retrieved, but no puzzles found)")
    if len(seasons) == 1:
        print(f"  Source: {season_url(seasons[0])}")
    elif seasons:
        print("  Sources:")
        for season in seasons:
            print(f"    {season_url(season)}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""Spoiler-free command-line interface.

Per Constitution Principle II, the CLI reports counts and provenance to stdout
and diagnostics/errors to stderr, and never prints puzzle solutions. Puzzle text
surfaces only behind the test boundary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wheeldb.episodes import extract_episode
from wheeldb.errors import DatabaseError, GameError, RetrievalError
from wheeldb.fetch import FileFetcher, season_url
from wheeldb.gamegen import generate_game
from wheeldb.ingest import ingest_seasons, parse_season_arg
from wheeldb.models import PuzzleParseError
from wheeldb.storage import PuzzleStore


def _add_from_dir(subparser) -> None:
    """Add the shared ``--from-dir`` option to a subcommand parser.

    Parameters:
        subparser: the ``episode`` or ``ingest`` subparser to extend.

    The flag points at a directory of season pages saved by hand from a browser
    (the live host gates the compendium behind a JS proof-of-work challenge);
    when given, the CLI reads those files instead of making any network request.
    """
    subparser.add_argument(
        "--from-dir",
        metavar="DIR",
        help="Read season pages from compendium{N}.html files saved in DIR "
        "(no network request).",
    )


def _csv_output_path(db_path: str) -> str:
    """Derive the CSV output path from the database path argument (FR-002a).

    Parameters:
        db_path: the ``--db`` path value (e.g. ``wheeldb.sqlite``).
    Returns:
        The same path with its final extension replaced by ``.csv`` (e.g.
        ``wheeldb.sqlite`` -> ``wheeldb.csv``); a path with no recognized
        extension has ``.csv`` appended (``wheeldb`` -> ``wheeldb.csv``).
    """
    return str(Path(db_path).with_suffix(".csv"))


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
    _add_from_dir(episode)

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
    ingest.add_argument(
        "--format",
        choices=("sqlite", "csv"),
        default="sqlite",
        help="Output format (default: sqlite). With 'csv', the output is written "
        "to the --db path with its extension swapped to .csv.",
    )
    _add_from_dir(ingest)

    game = sub.add_parser(
        "game",
        help="Generate a ready-to-play game (games/wof[N].pptm) from a season.",
    )
    game.add_argument("season", type=int, help="Season to draw puzzles from.")
    game.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional integer seed for reproducible puzzle selection.",
    )
    game.add_argument(
        "--db",
        default="wheeldb.sqlite",
        help="SQLite store to read (default: wheeldb.sqlite in the CWD).",
    )
    game.add_argument(
        "--games-dir",
        default="games",
        help="Output directory for the generated game (default: games; created if absent).",
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

    if fetcher is None and getattr(args, "from_dir", None):
        fetcher = FileFetcher(args.from_dir)

    if args.command == "ingest":
        return _run_ingest(args, fetcher)

    if args.command == "game":
        return _run_game(args)

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
        args: parsed arguments carrying ``seasons`` (the raw season/range string),
            ``db`` (the database path), and ``format`` (``sqlite`` or ``csv``).
        fetcher: optional ``Fetcher`` injected for offline testing.
    Returns:
        Exit code: 0 on a fully clean run; 2 on a bad argument, a skipped season,
        or a halting data/database error.
    """
    try:
        seasons = parse_season_arg(args.seasons)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("usage: wheeldb ingest <season|range> [--db PATH] [--format {sqlite,csv}]",
              file=sys.stderr)
        return 2

    out_path = _csv_output_path(args.db) if args.format == "csv" else args.db
    try:
        summary = ingest_seasons(
            seasons, db_path=out_path, fetcher=fetcher, store_format=args.format
        )
    except PuzzleParseError as exc:
        print(f"error: cannot derive puzzle number: {exc}", file=sys.stderr)
        return 2
    except DatabaseError as exc:
        print(f"error: database error: {exc}", file=sys.stderr)
        return 2

    _print_ingest_summary(summary, out_path)
    return 2 if (summary.skipped or summary.unparsed) else 0


def _run_game(args) -> int:
    """Execute the ``game`` subcommand, printing a spoiler-free summary.

    Generates ``<games-dir>/wof[N].pptm`` from the named season and reports only the
    created file and the fixed slot counts — never a solution or category (FR-009,
    Decision 6/7). Any generation failure (template missing, season absent,
    insufficient puzzles of a type, no number available, slot anchor missing) maps to
    a clear stderr message and exit 2; each failure mode is distinguishable (FR-014).

    Parameters:
        args: parsed arguments carrying ``season``, ``seed``, ``db``, ``games_dir``.
    Returns:
        Exit code: 0 on a created game file; 2 on any ``GameError`` or store error.
    """
    try:
        with PuzzleStore(args.db) as store:
            out_path = generate_game(
                args.season,
                store=store,
                games_dir=args.games_dir,
                seed=args.seed,
            )
    except (GameError, DatabaseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Created {out_path} from season {args.season}")
    print("  Puzzles: 4 Round, 3 Toss-Up, 1 Bonus Round (8 total)")
    return 0


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

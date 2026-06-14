"""Spoiler-free command-line interface.

Per Constitution Principle II, the CLI reports counts and provenance to stdout
and diagnostics/errors to stderr, and never prints puzzle solutions. Puzzle text
surfaces only behind the test boundary.
"""

from __future__ import annotations

import argparse
import sys

from wheeldb.episodes import extract_episode
from wheeldb.errors import RetrievalError
from wheeldb.fetch import season_url


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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

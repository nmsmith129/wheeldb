"""Test-only rendering of puzzles (including solutions).

This module lives under ``tests/`` on purpose: per Constitution Principle II, no
``src/wheeldb`` code path may print puzzle solutions. Solutions surface only here,
behind the test boundary, and only when a human opts in via ``--print-puzzles``.
"""

import sys


def render_puzzle(puzzle) -> str:
    """Render a single puzzle's attributes (including its solution) as one line.

    Parameters:
        puzzle: a ``Puzzle`` instance to render.
    Returns:
        A human-readable string showing season, episode, round, category, date,
        and the solution.
    """
    return (
        f"S{puzzle.season} E{puzzle.episode} {puzzle.round} "
        f"[{puzzle.category}] {puzzle.date} :: {puzzle.solution}"
    )


def print_puzzles(puzzles, stream=None) -> None:
    """Print each puzzle's attributes (including solutions) to a stream.

    Parameters:
        puzzles: an iterable of ``Puzzle`` instances.
        stream: text stream to write to; defaults to ``sys.stdout``.
    """
    out = stream if stream is not None else sys.stdout
    for puzzle in puzzles:
        print(render_puzzle(puzzle), file=out)

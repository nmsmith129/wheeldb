"""Tests for the test-only puzzle print option (US3).

Proves the spoiler boundary in both directions: the print helper renders every
attribute including the solution (so ``pytest --print-puzzles`` shows them), while
the option defaults off so solutions are not emitted unless a human opts in
(FR-012 / FR-013 / Principle II).
"""

from wheeldb.models import Puzzle
from print_helpers import print_puzzles, render_puzzle

_SAMPLE = [
    Puzzle("OPENING NIGHT", "Show Biz", "2024-09-09", 42, 8011, "T1"),
    Puzzle("DIGITAL FOOTPRINT", "Thing", "2024-09-09", 42, 8011, "BR"),
]


def test_render_includes_every_attribute_and_solution():
    """render_puzzle shows season, episode, round, category, date, and solution."""
    line = render_puzzle(_SAMPLE[0])
    print(f"rendered: {line}")
    for token in ("S42", "8011", "T1", "Show Biz", "2024-09-09", "OPENING NIGHT"):
        assert token in line


def test_print_puzzles_emits_solutions(capsys):
    """print_puzzles writes each puzzle's solution to the stream (opt-in path)."""
    print_puzzles(_SAMPLE)
    out = capsys.readouterr().out
    print(f"captured print_puzzles output:\n{out}")
    assert "OPENING NIGHT" in out
    assert "DIGITAL FOOTPRINT" in out


def test_print_option_defaults_off(maybe_print_puzzles, capsys):
    """Without --print-puzzles, the printer is a no-op (no solutions leak)."""
    maybe_print_puzzles(_SAMPLE)
    out = capsys.readouterr().out
    print(f"no-op printer output (should be empty): {out!r}")
    assert "OPENING NIGHT" not in out
    assert out == ""

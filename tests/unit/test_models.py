"""Unit tests for the Puzzle value object (US2).

Verifies the six required attributes, the round_name/puzzle_type derivations,
flag preservation, and (season, episode, round, solution) uniqueness semantics.
"""

from wheeldb.models import Puzzle


def _puzzle(**overrides):
    """Build a Puzzle with sensible defaults, overriding specific fields.

    Parameters:
        **overrides: field values to replace in the default puzzle.
    Returns:
        A ``Puzzle`` instance for use in assertions.
    """
    base = dict(
        solution="OPENING NIGHT",
        category="Show Biz",
        date="2024-09-09",
        season=42,
        episode=8011,
        round="T1",
        flags=(),
    )
    base.update(overrides)
    return Puzzle(**base)


def test_puzzle_exposes_six_attributes():
    """All six required attributes are present and carry the given values."""
    p = _puzzle()
    print(f"puzzle = {p}")
    assert p.solution == "OPENING NIGHT"
    assert p.category == "Show Biz"
    assert p.date == "2024-09-09"
    assert p.season == 42
    assert p.episode == 8011
    assert p.round == "T1"


def test_round_name_and_type_derivations():
    """round_name expands the code; puzzle_type is the coarse category."""
    cases = [
        ("T1", "Toss-Up 1", "Toss-Up"),
        ("T5", "Toss-Up 5", "Toss-Up"),
        ("R2", "Round 2", "Round"),
        ("R10", "Round 10", "Round"),
        ("BR", "Bonus Round", "Bonus Round"),
    ]
    for code, name, ptype in cases:
        p = _puzzle(round=code)
        print(f"round {code!r} -> name {p.round_name!r}, type {p.puzzle_type!r}")
        assert p.round_name == name
        assert p.puzzle_type == ptype


def test_flags_preserved_and_excluded_from_equality():
    """Annotation flags are kept but do not affect equality/uniqueness."""
    plain = _puzzle(round="R3")
    flagged = _puzzle(round="R3", flags=(("round", "*"),))
    print(f"flags on flagged = {flagged.flags}; equal to plain? {plain == flagged}")
    assert flagged.flags == (("round", "*"),)
    assert plain == flagged  # flags excluded from comparison


def test_uniqueness_key_distinguishes_solution():
    """Same season/episode/round but different solution are distinct puzzles."""
    a = _puzzle(round="R3", solution="GRAND PRIZE GETAWAY")
    b = _puzzle(round="R3", solution="SOMETHING ELSE")
    print(f"a == b? {a == b}; set size = {len({a, b})}")
    assert a != b
    assert len({a, b}) == 2

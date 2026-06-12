"""Tests for the HTML parsing and normalisation helpers.

These prove the scraper turns compendium markup into correct, normalised puzzle
records, which is the part most likely to break when the site's layout changes.
"""

import pytest

from wheeldb import (
    derive_puzzle_type,
    normalize_date,
    parse_index,
    parse_season,
)


def test_parse_index_returns_sorted_unique_seasons(index_html):
    """parse_index should return each season once, sorted, with absolute URLs."""
    seasons = parse_index(index_html)
    assert seasons == [
        (40, "https://buyavowel.boards.net/page/compendium40"),
        (41, "https://buyavowel.boards.net/page/compendium41"),
        (42, "https://buyavowel.boards.net/page/compendium42"),
    ]


def test_parse_season_extracts_all_puzzles(season_html):
    """parse_season should find every puzzle row and skip header/notes rows."""
    puzzles = parse_season(season_html, season=42, source_url="http://x/42")
    # 5 puzzles in episode 7001 + 4 in episode 7002, notes row ignored.
    assert len(puzzles) == 9
    assert all(p["season"] == 42 for p in puzzles)
    assert all(p["source_url"] == "http://x/42" for p in puzzles)


def test_parse_season_first_row_fields(season_html):
    """The first puzzle row should carry its episode context and exact fields."""
    first = parse_season(season_html, 42, "http://x/42")[0]
    assert first == {
        "season": 42,
        "episode": "7001",
        "air_date": "2024-09-09",
        "round_name": "Toss-Up 1",
        "puzzle_type": "Toss-Up",
        "category": "Phrase",
        "solution": "BREAK A LEG",
        "source_url": "http://x/42",
    }


def test_parse_season_carries_episode_context_forward(season_html):
    """Puzzles should inherit the most recent episode header's number/date."""
    puzzles = parse_season(season_html, 42, "http://x/42")
    ep2 = [p for p in puzzles if p["episode"] == "7002"]
    assert len(ep2) == 4
    assert all(p["air_date"] == "2024-09-10" for p in ep2)
    # Solution with an ampersand-bearing category survives cleaning.
    before_after = next(p for p in puzzles if p["round_name"] == "Round 2")
    assert before_after["category"] == "Before & After"
    assert before_after["solution"] == "PUMPKIN PIE CHART"


@pytest.mark.parametrize(
    "round_name,expected",
    [
        ("Toss-Up 1", "Toss-Up"),
        ("Toss-Up 2", "Toss-Up"),
        ("Round 2", "Round"),
        ("Round 10", "Round"),
        ("Triple Toss-Up A", "Triple Toss-Up"),
        ("Bonus Round", "Bonus Round"),
        ("Prize Puzzle", "Prize Puzzle"),
    ],
)
def test_derive_puzzle_type(round_name, expected):
    """derive_puzzle_type strips trailing instance markers, keeps base type."""
    assert derive_puzzle_type(round_name) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("September 19, 2024", "2024-09-19"),
        ("Sep 19, 2024", "2024-09-19"),
        ("09/19/2024", "2024-09-19"),
        ("09/19/24", "2024-09-19"),
        ("2024-09-19", "2024-09-19"),
    ],
)
def test_normalize_date_valid(raw, expected):
    """Known date formats normalise to ISO YYYY-MM-DD."""
    assert normalize_date(raw) == expected


def test_normalize_date_empty_is_none():
    """Empty/whitespace input yields None rather than a bogus date."""
    assert normalize_date("") is None
    assert normalize_date("   ") is None


def test_normalize_date_unparseable_preserved():
    """An unrecognised date string is returned as-is, not dropped."""
    assert normalize_date("sometime in 2024") == "sometime in 2024"

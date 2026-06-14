"""Integration tests for extract_episode over the offline fixtures (US1).

Proves the episode-number -> puzzles flow end-to-end: the documented S42 #8011
returns its three puzzles in order, an early-era episode parses, a non-existent
episode yields an empty list, and a retrieval failure raises (not an empty list).
"""

import pytest

from wheeldb.episodes import extract_episode
from wheeldb.errors import RetrievalError


def test_extract_documented_episode_8011(fetcher, maybe_print_puzzles):
    """S42 #8011 returns exactly the three documented puzzles, in round order."""
    puzzles = extract_episode(8011, fetcher=fetcher)
    maybe_print_puzzles(puzzles)
    summary = [(p.round, p.solution, p.category) for p in puzzles]
    print(f"extract_episode(8011) -> {summary}")
    assert [p.round for p in puzzles] == ["T1", "R2", "BR"]
    assert [p.solution for p in puzzles] == [
        "OPENING NIGHT",
        "ANIMATED SHORT ATTENTION SPAN",
        "DIGITAL FOOTPRINT",
    ]
    assert all(p.season == 42 and p.episode == 8011 for p in puzzles)


def test_extract_uses_available_seasons_when_unbounded(fetcher):
    """With no explicit seasons, the fetcher's available_seasons bounds the search."""
    puzzles = extract_episode(8011, fetcher=fetcher)  # no seasons= passed
    print(f"found {len(puzzles)} puzzles via available_seasons()")
    assert len(puzzles) == 3


def test_extract_early_era_episode(fetcher, maybe_print_puzzles):
    """An early-era episode (S1 #1) parses with unquoted solutions and a date flag."""
    puzzles = extract_episode(1, fetcher=fetcher, seasons=[1])
    maybe_print_puzzles(puzzles)
    print(f"S1 #1 rounds = {[p.round for p in puzzles]}")
    assert [p.round for p in puzzles] == ["R1", "R2", "R3", "BR"]
    assert puzzles[0].solution == "BURT LANCASTER"
    assert all(p.season == 1 and p.episode == 1 for p in puzzles)


def test_nonexistent_episode_returns_empty(fetcher):
    """An episode in no searched season yields [] (not an error)."""
    puzzles = extract_episode(99999, fetcher=fetcher, seasons=[1, 42])
    print(f"extract_episode(99999) -> {puzzles!r}")
    assert puzzles == []


def test_retrieval_failure_raises_not_empty():
    """A fetcher that fails raises RetrievalError, distinct from 'not found'."""

    class _FailingFetcher:
        def get_season_html(self, season_number):
            raise RetrievalError(f"HTTP 403 for season {season_number}")

    with pytest.raises(RetrievalError):
        extract_episode(8011, fetcher=_FailingFetcher(), seasons=[42])

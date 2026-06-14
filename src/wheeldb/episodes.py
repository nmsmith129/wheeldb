"""Episode-level retrieval orchestration.

``extract_episode`` is the feature's headline entry point: given a global episode
number it searches compendium season pages, matches the EP# column, and returns
that episode's puzzles. The compendium has no per-episode page, so this owns the
season lookup (FR-004).
"""

from __future__ import annotations

from wheeldb.errors import ParseError
from wheeldb.fetch import HttpFetcher
from wheeldb.models import Puzzle
from wheeldb.parser import find_puzzle_table, parse_rows

#: Highest season to search when a fetcher does not declare its own range.
DEFAULT_MAX_SEASON = 43


def extract_episode(episode_number: int, *, fetcher=None, seasons=None) -> list[Puzzle]:
    """Return every puzzle that aired in the given episode.

    Searches season pages in ascending order, matching the normalized EP# value.
    Because an episode belongs to exactly one season, the first season with a
    match is returned immediately; the search also stops once a season's episodes
    have passed the target (episode numbers increase with air date).

    Parameters:
        episode_number: the show's global episode number (EP# without ``#``).
        fetcher: a ``Fetcher`` providing season HTML; defaults to a live
            ``HttpFetcher``. Tests inject a fixture-backed fetcher.
        seasons: optional explicit iterable of season numbers to search. When
            omitted, the fetcher's ``available_seasons()`` is used if present,
            otherwise seasons 1..``DEFAULT_MAX_SEASON``.
    Returns:
        A list of ``Puzzle`` objects in round order, or an empty list if the
        episode appears in no searched season (FR-010).
    Raises:
        RetrievalError: a season page could not be retrieved (FR-011).
    """
    if fetcher is None:
        fetcher = HttpFetcher()

    if seasons is None:
        available = getattr(fetcher, "available_seasons", None)
        seasons = available() if callable(available) else range(1, DEFAULT_MAX_SEASON + 1)

    for season in sorted(seasons):
        html = fetcher.get_season_html(season)  # RetrievalError propagates
        try:
            table = find_puzzle_table(html)
        except ParseError:
            continue  # page without a recognizable puzzle table; skip it

        puzzles = parse_rows(table, season)
        matches = [p for p in puzzles if p.episode == episode_number]
        if matches:
            return matches

        episodes_here = [p.episode for p in puzzles]
        if episodes_here and min(episodes_here) > episode_number:
            break  # we have passed the target episode's era

    return []

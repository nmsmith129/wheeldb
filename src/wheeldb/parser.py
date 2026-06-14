"""Parse a season page's HTML into Puzzle objects.

Selects the puzzle table by its header signature (so navigation/legend tables are
skipped, per FORMAT.md) and converts each data row into a normalized ``Puzzle``
using the single-source helpers in :mod:`wheeldb.normalize`.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from wheeldb.errors import ParseError
from wheeldb.models import Puzzle
from wheeldb.normalize import (
    normalize_category,
    normalize_date,
    normalize_episode,
    normalize_round,
    normalize_solution,
)

#: The fixed 5-column header that identifies the puzzle table.
HEADER_SIGNATURE = ["PUZZLE", "CATEGORY", "DATE", "EP#", "ROUND"]


def _row_cells(row) -> list[str]:
    """Return the trimmed text of each cell in a table row.

    Parameters:
        row: a BeautifulSoup ``<tr>`` element.
    Returns:
        The text of each ``<td>``/``<th>`` in order, whitespace-stripped.
    """
    return [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]


def _is_header(cells: list[str]) -> bool:
    """Report whether a row's cells are the puzzle-table header.

    Parameters:
        cells: the trimmed cell texts of a row.
    Returns:
        True if the first five cells match the PUZZLE/CATEGORY/DATE/EP#/ROUND
        signature (case-insensitively).
    """
    return [c.upper() for c in cells[:5]] == HEADER_SIGNATURE


def find_puzzle_table(html: str):
    """Locate the puzzle table within a season page.

    Parameters:
        html: raw HTML of a compendium season page.
    Returns:
        The BeautifulSoup ``<table>`` element whose header row matches the puzzle
        signature.
    Raises:
        ParseError: no table with the expected header signature was found.
    """
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            if _is_header(_row_cells(row)):
                return table
    raise ParseError(
        "no puzzle table found (expected header "
        "PUZZLE/CATEGORY/DATE/EP#/ROUND)"
    )


def parse_rows(table, season: int) -> list[Puzzle]:
    """Parse each data row of a puzzle table into a Puzzle.

    Parameters:
        table: the puzzle table returned by :func:`find_puzzle_table`.
        season: the season number for this page (sets ``Puzzle.season``).
    Returns:
        One ``Puzzle`` per data row, in source (round) order. The header row and
        rows with an empty/malformed PUZZLE or EP# cell are skipped.
    """
    puzzles: list[Puzzle] = []
    header_seen = False
    for row in table.find_all("tr"):
        cells = _row_cells(row)
        if _is_header(cells):
            header_seen = True
            continue
        if not header_seen or len(cells) < 5:
            continue

        solution = normalize_solution(cells[0])
        if not solution:
            continue  # empty PUZZLE cell: not a puzzle row

        flags: list[tuple[str, str]] = []
        date_value, date_flag = normalize_date(cells[2])
        if date_flag:
            flags.append(("date", date_flag))
        round_code, round_flag = normalize_round(cells[4])
        if round_flag:
            flags.append(("round", round_flag))
        try:
            episode = normalize_episode(cells[3])
        except ValueError:
            continue  # malformed EP#: skip defensively

        puzzles.append(
            Puzzle(
                solution=solution,
                category=normalize_category(cells[1]),
                date=date_value,
                season=season,
                episode=episode,
                round=round_code,
                flags=tuple(flags),
            )
        )
    return puzzles

"""Single source of truth for normalizing compendium cell values.

Per Constitution Principle IV (Reuse Before Creation), all puzzle-field
normalization lives here so the rules cannot drift apart. Rules follow FORMAT.md
and the feature's clarifications: strip surrounding quotes from solutions, strip
trailing annotation symbols off dates/rounds, normalize dates to ISO, keep the
round as its clean raw code.
"""

from __future__ import annotations

import re
from datetime import date

#: Quote characters stripped from the ends of a solution (straight and curly).
_QUOTES = '"“”'

#: M/D/YY or M/D/YYYY, the date forms used on the compendium.
_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$")

#: 2-digit-year pivot: years >= this map to the 1900s, else the 2000s.
_YEAR_PIVOT = 83


def normalize_solution(raw: str) -> str:
    """Normalize a PUZZLE cell into a clean solution string.

    Parameters:
        raw: the raw PUZZLE cell text, possibly quoted and/or padded.
    Returns:
        The solution with surrounding double quotes (straight or curly) and
        whitespace removed.
    """
    value = raw.strip()
    if len(value) >= 2 and value[0] in _QUOTES and value[-1] in _QUOTES:
        value = value[1:-1].strip()
    return value


def normalize_category(raw: str) -> str:
    """Normalize a CATEGORY cell.

    Parameters:
        raw: the raw CATEGORY cell text.
    Returns:
        The category with surrounding whitespace removed.
    """
    return raw.strip()


def normalize_date(raw: str) -> tuple[str, str | None]:
    """Normalize a DATE cell to ISO form, separating any annotation symbol.

    Strips a trailing ``*`` (recording it as a flag), then parses ``M/D/YY`` (or
    ``M/D/YYYY``) to ISO ``YYYY-MM-DD`` using the 2-digit-year pivot. If the value
    cannot be parsed it is returned unchanged (FR-015).

    Parameters:
        raw: the raw DATE cell text (e.g. ``9/9/24`` or ``9/19/83*``).
    Returns:
        A ``(value, flag)`` tuple: ``value`` is the ISO date when parseable, else
        the de-annotated raw text; ``flag`` is ``"*"`` if one was present, else
        ``None``.
    """
    value = raw.strip()
    flag: str | None = None
    if value.endswith("*"):
        flag = "*"
        value = value[:-1].strip()

    match = _DATE_RE.match(value)
    if match:
        month, day, year = (int(g) for g in match.groups())
        if year < 100:
            year = 1900 + year if year >= _YEAR_PIVOT else 2000 + year
        try:
            return date(year, month, day).isoformat(), flag
        except ValueError:
            pass  # impossible calendar date: fall through and keep raw text
    return value, flag


def normalize_round(raw: str) -> tuple[str, str | None]:
    """Normalize a ROUND cell into a clean code, separating any annotation.

    Parameters:
        raw: the raw ROUND cell text (e.g. ``T1``, ``R3*``, ``R2^``).
    Returns:
        A ``(code, flag)`` tuple: ``code`` is the clean round code with any
        trailing ``*``/``^`` removed; ``flag`` is that symbol, or ``None``.
    """
    value = raw.strip()
    flag: str | None = None
    if value and value[-1] in "*^":
        flag = value[-1]
        value = value[:-1].strip()
    return value, flag


def normalize_episode(raw: str) -> int:
    """Normalize an EP# cell into an integer episode number.

    Parameters:
        raw: the raw EP# cell text (e.g. ``#8011``).
    Returns:
        The episode number as an ``int`` (leading ``#`` removed).
    Raises:
        ValueError: the cell does not contain a valid integer after the ``#``.
    """
    return int(raw.strip().lstrip("#").strip())

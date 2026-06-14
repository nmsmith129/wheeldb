"""Unit tests for the ingest season-argument parser (``wheeldb.ingest.parse_season_arg``).

The ingest command accepts only a single season (``"40"``) or an inclusive
ascending range (``"37-40"``); everything else is rejected. Debug output prints
the input and the result/exception at the point of failure (Principle V).
"""

from __future__ import annotations

import pytest

from wheeldb.ingest import parse_season_arg


@pytest.mark.parametrize(
    "text, expected",
    [
        ("40", [40]),
        ("37-40", [37, 38, 39, 40]),
        ("40-40", [40]),
        ("1-3", [1, 2, 3]),
    ],
)
def test_parse_season_arg_accepts_season_and_range(text, expected):
    """Valid single seasons and inclusive ranges expand to the right season list."""
    result = parse_season_arg(text)
    print(f"input {text!r} -> {result} (expected {expected})")
    assert result == expected


@pytest.mark.parametrize("text", ["40-37", "", "abc", "-5", "3-", "a-b", "37-", "-", "40-41-42"])
def test_parse_season_arg_rejects_malformed_or_reversed(text):
    """Malformed arguments and reversed ranges raise ValueError."""
    print(f"input {text!r} -> expecting ValueError")
    with pytest.raises(ValueError):
        parse_season_arg(text)

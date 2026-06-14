"""Unit tests for the single-source normalization helpers (US2).

Covers quote stripping, category trimming, date ISO conversion with the year
pivot and raw fallback, annotation-symbol stripping, and episode parsing. Each
assertion prints input/expected/actual so a failure is diagnosable from the log
(Constitution Principle V).
"""

import pytest

from wheeldb.normalize import (
    normalize_category,
    normalize_date,
    normalize_episode,
    normalize_round,
    normalize_solution,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"OPENING NIGHT"', "OPENING NIGHT"),
        ("BURT LANCASTER", "BURT LANCASTER"),
        ("  A STITCH IN TIME  ", "A STITCH IN TIME"),
        ("“CURLY QUOTED”", "CURLY QUOTED"),
        ('"MALCOLM IN THE MIDDLE AGES"', "MALCOLM IN THE MIDDLE AGES"),
    ],
)
def test_normalize_solution_strips_quotes(raw, expected):
    """Surrounding straight/curly quotes and padding are removed."""
    actual = normalize_solution(raw)
    print(f"normalize_solution({raw!r}) -> expected {expected!r}, got {actual!r}")
    assert actual == expected


def test_normalize_category_trims():
    """A category is returned trimmed, ampersands intact."""
    actual = normalize_category(" Before & After ")
    print(f"normalize_category -> expected 'Before & After', got {actual!r}")
    assert actual == "Before & After"


@pytest.mark.parametrize(
    "raw,expected_value,expected_flag",
    [
        ("9/9/24", "2024-09-09", None),
        ("9/19/83", "1983-09-19", None),
        ("9/19/83*", "1983-09-19", "*"),
        ("12/31/82", "2082-12-31", None),  # 82 < pivot 83 -> 2000s
        ("1/1/83", "1983-01-01", None),    # 83 == pivot -> 1900s
        ("9/9/2024", "2024-09-09", None),  # 4-digit year tolerated
        ("sometime in 2024", "sometime in 2024", None),  # unparseable kept raw
    ],
)
def test_normalize_date(raw, expected_value, expected_flag):
    """Dates convert to ISO with the year pivot; unparseable text is preserved."""
    value, flag = normalize_date(raw)
    print(
        f"normalize_date({raw!r}) -> expected ({expected_value!r},{expected_flag!r}), "
        f"got ({value!r},{flag!r})"
    )
    assert (value, flag) == (expected_value, expected_flag)


@pytest.mark.parametrize(
    "raw,expected_code,expected_flag",
    [
        ("T1", "T1", None),
        ("R2", "R2", None),
        ("BR", "BR", None),
        ("R3*", "R3", "*"),
        ("R2^", "R2", "^"),
    ],
)
def test_normalize_round(raw, expected_code, expected_flag):
    """Round codes keep their clean form; trailing */^ become flags."""
    code, flag = normalize_round(raw)
    print(
        f"normalize_round({raw!r}) -> expected ({expected_code!r},{expected_flag!r}), "
        f"got ({code!r},{flag!r})"
    )
    assert (code, flag) == (expected_code, expected_flag)


@pytest.mark.parametrize("raw,expected", [("#8011", 8011), ("#1", 1), (" #42 ", 42)])
def test_normalize_episode(raw, expected):
    """Episode numbers drop the leading '#' and parse to int."""
    actual = normalize_episode(raw)
    print(f"normalize_episode({raw!r}) -> expected {expected}, got {actual}")
    assert actual == expected


def test_normalize_episode_rejects_non_numeric():
    """A non-numeric EP# raises ValueError (caller skips such rows)."""
    with pytest.raises(ValueError):
        normalize_episode("#TBD")

"""Shared pytest fixtures.

Centralises access to the saved sample HTML pages so every test module reads
them the same way and a single path change updates them all.
"""

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    """Read a fixture HTML file by name.

    A tiny helper so tests reference fixtures by short name rather than repeating
    the directory path.
    """
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def index_html() -> str:
    """The representative compendium index page used by parser/CLI tests."""
    return _read("index.html")


@pytest.fixture
def season_html() -> str:
    """The representative single-season page used by parser/CLI tests."""
    return _read("season42.html")

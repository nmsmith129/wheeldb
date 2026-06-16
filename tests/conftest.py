"""Shared pytest fixtures and the test-only print option.

Centralizes access to the saved sample HTML pages and provides an offline
``Fetcher`` so the whole suite runs without touching the live site (Constitution
Principle I). Also registers the ``--print-puzzles`` option (Principle V / FR-012)
whose rendering lives in :mod:`print_helpers`.
"""

import shutil
from pathlib import Path

import pytest

from wheeldb.errors import RetrievalError
from print_helpers import print_puzzles

FIXTURE_DIR = Path(__file__).parent / "fixtures"

#: The macro-enabled template at the repo root, treated read-only by tests.
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "WheelofFortune6.4.pptm"


def _read(name: str) -> str:
    """Read a fixture HTML file by name.

    Parameters:
        name: file name under ``tests/fixtures`` (e.g. ``compendium42.html``).
    Returns:
        The file's text decoded as UTF-8.
    """
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class FixtureFetcher:
    """An offline ``Fetcher`` that serves saved season-page fixtures.

    Stands in for the live HTTP fetcher so parser/lookup tests run without
    network access.
    """

    def __init__(self, seasons=(1, 20, 42)):
        """Create a fetcher backed by the given season fixtures.

        Parameters:
            seasons: season numbers for which a ``compendium{N}.html`` fixture
                exists and may be served.
        """
        self._seasons = list(seasons)

    def get_season_html(self, season_number: int) -> str:
        """Return the saved HTML for a season page.

        Parameters:
            season_number: the season whose fixture to read.
        Returns:
            Raw HTML text of the season page fixture.
        Raises:
            RetrievalError: no fixture is configured for ``season_number``.
        """
        if season_number not in self._seasons:
            raise RetrievalError(f"no fixture for season {season_number}")
        return _read(f"compendium{season_number}.html")

    def available_seasons(self):
        """Return the season numbers this fetcher can serve.

        Returns:
            The list of seasons with a configured fixture, used by
            ``extract_episode`` to bound its search offline.
        """
        return list(self._seasons)


class RecordingFetcher:
    """An offline ``Fetcher`` that records requested seasons and can simulate gaps.

    Like :class:`FixtureFetcher` but (a) it remembers every season it was asked
    for (in ``requested``) so bounded-fetch tests can assert the scraper stayed
    within the requested range, and (b) it accepts a ``files`` mapping so an
    arbitrary season number can be aliased to any existing fixture file. A season
    that is neither ``available`` nor in ``files`` raises ``RetrievalError`` when
    requested, which lets best-effort skip tests model an unretrievable season.
    """

    def __init__(self, available=(1, 20, 42), *, files=None):
        """Create a recording fetcher.

        Parameters:
            available: season numbers served from their default
                ``compendium{N}.html`` fixture.
            files: optional ``{season: fixture_filename}`` mapping that aliases a
                season number to a specific fixture file (overrides the default
                name and extends the set of served seasons).
        """
        self._available = dict.fromkeys(available)
        self._files = dict(files or {})
        self.requested: list[int] = []

    def get_season_html(self, season_number: int) -> str:
        """Return the saved HTML for a season page, recording the request.

        Parameters:
            season_number: the season whose fixture to read.
        Returns:
            Raw HTML text of the mapped season-page fixture.
        Raises:
            RetrievalError: the season is neither served nor aliased (models an
                unretrievable season page).
        """
        self.requested.append(season_number)
        if season_number in self._files:
            return _read(self._files[season_number])
        if season_number in self._available:
            return _read(f"compendium{season_number}.html")
        raise RetrievalError(f"no fixture for season {season_number}")

    def available_seasons(self):
        """Return the season numbers this fetcher can serve.

        Returns:
            The served seasons (defaults plus any aliased via ``files``).
        """
        return list(self._available) + [s for s in self._files if s not in self._available]


@pytest.fixture
def fetcher() -> FixtureFetcher:
    """A fixture-backed fetcher serving the early/middle/recent era fixtures."""
    return FixtureFetcher([1, 20, 42])


@pytest.fixture
def template_pptm(tmp_path) -> Path:
    """Return a throwaway copy of the real ``WheelofFortune6.4.pptm`` template.

    Copies the repo's macro-enabled template into ``tmp_path`` so injection tests
    operate on a disposable source package offline (Constitution Principle I); the
    real template at the repo root is never written. Skips the test if the template
    is absent (it is a large binary not always present in a checkout).

    Parameters:
        tmp_path: pytest's per-test temporary directory.
    Returns:
        Path to the copied template inside ``tmp_path``.
    """
    if not TEMPLATE_PATH.exists():
        pytest.skip(f"template not found at {TEMPLATE_PATH}")
    dest = tmp_path / TEMPLATE_PATH.name
    shutil.copy2(TEMPLATE_PATH, dest)
    return dest


def pytest_addoption(parser):
    """Register the ``--print-puzzles`` command-line option.

    Parameters:
        parser: the pytest option parser provided by the plugin hook.
    """
    parser.addoption(
        "--print-puzzles",
        action="store_true",
        default=False,
        help="Print parsed puzzles (including solutions) to the test log.",
    )


@pytest.fixture
def maybe_print_puzzles(request):
    """Return a puzzle printer that is active only under ``--print-puzzles``.

    Parameters:
        request: the pytest request, used to read the ``--print-puzzles`` flag.
    Returns:
        ``print_puzzles`` when the flag is set, otherwise a no-op callable. This
        keeps puzzle solutions behind the test boundary (Principle II / FR-013).
    """
    if request.config.getoption("--print-puzzles"):
        return print_puzzles
    return lambda *args, **kwargs: None

"""HTTP retrieval of compendium season pages.

Defines the ``Fetcher`` seam (so the parser/lookup can run offline against saved
fixtures) and the live ``HttpFetcher`` that talks to buyavowel.boards.net with a
real browser User-Agent and a politeness delay, per the project's respectful-
scraping constraint.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol, runtime_checkable

import requests

from wheeldb.errors import RetrievalError

#: URL template for a season's compendium page; ``{n}`` is the season number.
SEASON_URL_TEMPLATE = "https://buyavowel.boards.net/page/compendium{n}"

#: A real desktop-browser User-Agent (the site returns HTTP 403 to other agents).
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def season_url(season_number: int) -> str:
    """Return the compendium page URL for a season.

    Parameters:
        season_number: the season number to build a URL for.
    Returns:
        The absolute ``.../page/compendium{N}`` URL.
    """
    return SEASON_URL_TEMPLATE.format(n=season_number)


@runtime_checkable
class Fetcher(Protocol):
    """Strategy for obtaining a season page's raw HTML.

    The default implementation fetches over HTTP; tests inject a fixture-backed
    implementation so the suite runs offline.
    """

    def get_season_html(self, season_number: int) -> str:
        """Return the raw HTML of the compendium page for ``season_number``.

        Parameters:
            season_number: the season page to retrieve.
        Returns:
            Raw HTML text of the season page.
        Raises:
            RetrievalError: the page could not be retrieved.
        """
        ...


class HttpFetcher:
    """Live ``Fetcher`` that downloads season pages over HTTP.

    Sends a browser User-Agent and waits a politeness delay between requests; a
    403 or any non-200 response becomes a ``RetrievalError``.
    """

    def __init__(self, session=None, delay: float = 1.0, user_agent: str = DEFAULT_USER_AGENT):
        """Create a live fetcher.

        Parameters:
            session: an object with a ``get(url, headers=, timeout=)`` method
                (defaults to a new ``requests.Session``); injectable for tests.
            delay: seconds to sleep after each request (politeness throttle).
            user_agent: the User-Agent header value to send.
        """
        self._session = session if session is not None else requests.Session()
        self._delay = delay
        self._user_agent = user_agent

    def get_season_html(self, season_number: int) -> str:
        """Fetch a season page's HTML over HTTP.

        Parameters:
            season_number: the season page to retrieve.
        Returns:
            The response body text.
        Raises:
            RetrievalError: on HTTP 403, any non-200 status, or a network error.
        """
        url = season_url(season_number)
        try:
            response = self._session.get(
                url, headers={"User-Agent": self._user_agent}, timeout=30
            )
        except requests.RequestException as exc:
            raise RetrievalError(f"network error retrieving {url}: {exc}") from exc
        finally:
            # Honor the politeness delay even when a request raises.
            time.sleep(self._delay)

        if response.status_code == 403:
            raise RetrievalError(
                f"retrieval blocked (HTTP 403) for {url}; a browser User-Agent "
                "is required and the host may be rate-limiting"
            )
        if response.status_code != 200:
            raise RetrievalError(
                f"unexpected HTTP {response.status_code} retrieving {url}"
            )
        return response.text


class FileFetcher:
    """Offline ``Fetcher`` that serves season pages saved to disk by hand.

    The live host now gates the compendium behind a JavaScript proof-of-work
    challenge (it answers a bare request with HTTP 202 and a challenge page, not
    the puzzle table). Rather than defeat that gate, this fetcher reads a page the
    user saved from a real browser: it looks for ``compendium{N}.html`` in a
    directory and returns its contents. No network request is made, so the
    respectful-scraping delay does not apply.
    """

    def __init__(self, directory):
        """Create a fetcher backed by a directory of saved season pages.

        Parameters:
            directory: path to a folder containing ``compendium{N}.html`` files
                saved manually from a browser.
        """
        self._directory = Path(directory)

    def get_season_html(self, season_number: int) -> str:
        """Return the saved HTML for a season page.

        Parameters:
            season_number: the season whose saved page to read.
        Returns:
            The text of ``compendium{season_number}.html`` in the directory.
        Raises:
            RetrievalError: no saved page exists for ``season_number`` (so the
                caller skips it, exactly as it would an unreachable network page).
        """
        path = self._directory / f"compendium{season_number}.html"
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RetrievalError(
                f"no saved page for season {season_number} at {path}; save the "
                "compendium page from a browser and place it there"
            ) from exc

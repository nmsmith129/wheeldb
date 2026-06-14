"""Unit tests for the live HTTP fetcher (US1).

Uses a fake session (no network) to prove the fetcher sends a browser
User-Agent, honors the politeness delay, and maps HTTP 403/non-200 to
RetrievalError.
"""

import pytest

import wheeldb.fetch as fetch_mod
from wheeldb.errors import RetrievalError
from wheeldb.fetch import HttpFetcher, season_url


class _FakeResponse:
    """A minimal stand-in for a requests Response."""

    def __init__(self, status_code, text="<html>ok</html>"):
        self.status_code = status_code
        self.text = text


class _FakeSession:
    """Records the last request and returns a preconfigured response."""

    def __init__(self, response):
        self._response = response
        self.last_url = None
        self.last_headers = None

    def get(self, url, headers=None, timeout=None):
        """Capture the request and return the canned response."""
        self.last_url = url
        self.last_headers = headers or {}
        return self._response


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Replace time.sleep with a recorder so tests neither sleep nor lose the delay."""
    calls = []
    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: calls.append(s))
    return calls


def test_fetch_sends_browser_user_agent(_no_real_sleep):
    """The request carries a Mozilla browser User-Agent (site 403s others)."""
    session = _FakeSession(_FakeResponse(200, "<html>season</html>"))
    html = HttpFetcher(session=session, delay=0).get_season_html(42)
    ua = session.last_headers.get("User-Agent", "")
    print(f"requested {session.last_url} with UA={ua!r}")
    assert session.last_url == season_url(42)
    assert "Mozilla/5.0" in ua
    assert html == "<html>season</html>"


def test_fetch_honors_politeness_delay(_no_real_sleep):
    """The configured delay is passed to time.sleep after the request."""
    session = _FakeSession(_FakeResponse(200))
    HttpFetcher(session=session, delay=1.5).get_season_html(42)
    print(f"sleep calls = {_no_real_sleep}")
    assert _no_real_sleep == [1.5]


def test_fetch_403_raises_retrieval_error(_no_real_sleep):
    """A 403 becomes a RetrievalError, not an empty/None result."""
    session = _FakeSession(_FakeResponse(403, "blocked"))
    with pytest.raises(RetrievalError) as exc:
        HttpFetcher(session=session, delay=0).get_season_html(42)
    print(f"403 raised: {exc.value}")
    assert "403" in str(exc.value)


def test_fetch_non_200_raises_retrieval_error(_no_real_sleep):
    """Any non-200 status is a retrieval failure."""
    session = _FakeSession(_FakeResponse(500, "oops"))
    with pytest.raises(RetrievalError):
        HttpFetcher(session=session, delay=0).get_season_html(42)

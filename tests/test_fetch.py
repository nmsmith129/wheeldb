"""Tests for the HTTP fetch layer.

These prove the network choke point behaves: it sends the browser User-Agent,
turns a 403 into the actionable egress error, retries transient failures with
backoff, and serves from the on-disk cache on a second call.
"""

import requests
import responses

from wheeldb import EgressBlockedError, fetch, make_session

URL = "https://buyavowel.boards.net/page/compendiumindex"


@responses.activate
def test_fetch_sends_browser_user_agent():
    """fetch must send a browser UA, since the site 403s other agents."""
    responses.add(responses.GET, URL, body="<html>ok</html>", status=200)
    fetch(make_session(), URL, delay=0)
    assert "Mozilla/5.0" in responses.calls[0].request.headers["User-Agent"]


@responses.activate
def test_fetch_403_raises_egress_error():
    """A 403 should raise the dedicated, actionable error (not be retried)."""
    responses.add(responses.GET, URL, body="blocked", status=403)
    try:
        fetch(make_session(), URL, delay=0)
    except EgressBlockedError as exc:
        assert "egress" in str(exc).lower() or "allowlist" in str(exc).lower()
    else:
        raise AssertionError("expected EgressBlockedError")
    # Exactly one call: a 403 is not retried.
    assert len(responses.calls) == 1


@responses.activate
def test_fetch_retries_transient_then_succeeds(monkeypatch):
    """A transient 503 should be retried, then return the eventual 200 body."""
    # Avoid real sleeping during retry/backoff so the test is fast.
    monkeypatch.setattr("wheeldb.time.sleep", lambda *_: None)
    responses.add(responses.GET, URL, body="oops", status=503)
    responses.add(responses.GET, URL, body="<html>good</html>", status=200)
    html = fetch(make_session(), URL, delay=0)
    assert "good" in html
    assert len(responses.calls) == 2


@responses.activate
def test_fetch_uses_cache_on_second_call(tmp_path):
    """A cached page should be returned without a second network request."""
    responses.add(responses.GET, URL, body="<html>cached</html>", status=200)
    session = make_session()
    first = fetch(session, URL, delay=0, cache_dir=tmp_path)
    second = fetch(session, URL, delay=0, cache_dir=tmp_path)
    assert first == second == "<html>cached</html>"
    # Only the first call hit the network; the second was served from disk.
    assert len(responses.calls) == 1

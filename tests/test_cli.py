"""End-to-end test of the full pipeline through ``main``.

Mocks HTTP to serve the saved fixtures, runs the CLI against a temp database, and
verifies the whole fetch -> parse -> upsert chain wires together and populates the
database with the expected rows.
"""

import sqlite3

import responses

import wheeldb
from wheeldb import INDEX_URL, main


@responses.activate
def test_main_builds_database(tmp_path, index_html, season_html):
    """Running the CLI for one season should populate the database end-to-end."""
    responses.add(responses.GET, INDEX_URL, body=index_html, status=200)
    responses.add(
        responses.GET,
        "https://buyavowel.boards.net/page/compendium42",
        body=season_html,
        status=200,
    )
    db_path = tmp_path / "puzzles.db"

    rc = main(["--db", str(db_path), "--seasons", "42", "--delay", "0"])
    assert rc == 0

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    distinct_types = {r[0] for r in conn.execute("SELECT DISTINCT puzzle_type FROM puzzles")}
    conn.close()

    assert count == 20  # all puzzles from the season42 fixture (2 episodes × 10)
    assert "Toss-Up" in distinct_types and "Round" in distinct_types


@responses.activate
def test_main_reports_egress_block(tmp_path, monkeypatch):
    """A 403 on the index should exit non-zero with the egress error path."""
    monkeypatch.setattr("wheeldb.time.sleep", lambda *_: None)
    responses.add(responses.GET, INDEX_URL, body="blocked", status=403)
    rc = main(["--db", str(tmp_path / "x.db"), "--delay", "0"])
    assert rc == 2

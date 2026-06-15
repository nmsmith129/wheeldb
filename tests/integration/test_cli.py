"""Integration tests for the spoiler-free CLI (US1).

Verifies stdout reports count + season + rounds + source and contains NO puzzle
solution text (Principle II / FR-013), that "not found" exits 0, and that a
retrieval failure exits non-zero with a stderr message.
"""

from wheeldb.cli import main
from wheeldb.errors import RetrievalError


def test_cli_reports_without_revealing_solutions(fetcher, capsys):
    """The episode report shows counts/provenance but never a solution."""
    rc = main(["episode", "8011"], fetcher=fetcher)
    out = capsys.readouterr().out
    print(f"rc={rc}; stdout=\n{out}")
    assert rc == 0
    assert "Season 42" in out
    assert "3 puzzles found" in out
    assert "T1, R2, BR" in out
    assert "compendium42" in out
    # Spoiler boundary: no solution text leaks to stdout.
    for solution in ("OPENING NIGHT", "ANIMATED SHORT ATTENTION SPAN", "DIGITAL FOOTPRINT"):
        assert solution not in out


def test_cli_not_found_exits_zero(fetcher, capsys):
    """A non-existent episode is a valid result: exit 0, count 0."""
    rc = main(["episode", "99999"], fetcher=fetcher)
    out = capsys.readouterr().out
    print(f"rc={rc}; stdout={out!r}")
    assert rc == 0
    assert "0 puzzles found" in out


def test_cli_retrieval_failure_exits_nonzero(capsys):
    """A retrieval failure exits 2 and writes an error to stderr."""

    class _FailingFetcher:
        def get_season_html(self, season_number):
            raise RetrievalError("HTTP 403")

    rc = main(["episode", "8011"], fetcher=_FailingFetcher())
    captured = capsys.readouterr()
    print(f"rc={rc}; stderr={captured.err!r}")
    assert rc == 2
    assert "could not retrieve" in captured.err


def test_cli_ingest_from_dir_reads_saved_pages(tmp_path, capsys):
    """`--from-dir` ingests a manually saved compendium page with no network."""
    db = tmp_path / "out.sqlite"
    pages = tmp_path / "pages"
    pages.mkdir()
    from pathlib import Path

    fixture = Path(__file__).parent.parent / "fixtures" / "compendium42.html"
    (pages / "compendium42.html").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["ingest", "42", "--db", str(db), "--from-dir", str(pages)])
    out = capsys.readouterr().out
    print(f"rc={rc}; stdout=\n{out}")
    assert rc == 0
    assert "season 42" in out
    assert db.exists()

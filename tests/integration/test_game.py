"""Integration tests for the ``wheeldb game`` subcommand (end-to-end generation).

Seeds a fixture season into a ``tmp_path`` SQLite store, runs the CLI, and asserts a
``wof[N].pptm`` is created, the run exits 0, stdout reports the file + slot counts and
is spoiler-free, and the real template is byte-unchanged (US1/US2). All offline; the
real ``WheelofFortune6.4.pptm`` is the template (skipped if absent). Debug output
prints the exit code and captured stdout/stderr (Constitution Principle V).
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from wheeldb import cli
from wheeldb.models import Puzzle
from wheeldb.storage import PuzzleStore

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "WheelofFortune6.4.pptm"


def _seed_season(db_path, *, season=42, rounds=6, tossups=5, bonus=3):
    """Seed a store with a full season of puzzles of each type.

    Parameters:
        db_path: path to the SQLite store to create.
        season: season number to file the puzzles under.
        rounds, tossups, bonus: counts of each type to create.
    Returns:
        The list of solutions and categories written (for spoiler scanning).
    """
    secrets = []
    with PuzzleStore(db_path) as store:
        with store.transaction():
            ep = 8000
            for i in range(1, rounds + 1):
                sol, cat = f"ROUNDWORD{i}", f"RoundCat{i}"
                store.upsert(Puzzle(sol, cat, "2024-01-01", season, ep, f"R{i}"))
                secrets += [sol, cat]
            for i in range(1, tossups + 1):
                sol, cat = f"TOSSWORD{i}", f"TossCat{i}"
                store.upsert(Puzzle(sol, cat, "2024-01-01", season, ep + i, f"T{i}"))
                secrets += [sol, cat]
            for i in range(bonus):
                sol, cat = f"BONUSWORD{i}", f"BonusCat{i}"
                store.upsert(Puzzle(sol, cat, "2024-01-01", season, 8100 + i, "BR"))
                secrets += [sol, cat]
    return secrets


def _digest(path):
    """Return the SHA-256 hex digest of a file's bytes.

    Parameters:
        path: file to hash.
    Returns:
        Hex digest string.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def template(tmp_path):
    """Skip unless the real template exists; return its path."""
    if not TEMPLATE_PATH.exists():
        pytest.skip(f"template not found at {TEMPLATE_PATH}")
    return TEMPLATE_PATH


# --- T011: end-to-end generation (US1) ----------------------------------------

def test_game_creates_wof001_and_reports_spoiler_free(template, tmp_path, capsys):
    """A run on a seeded season creates wof001.pptm, exits 0, and prints no spoilers."""
    db = tmp_path / "store.sqlite"
    games = tmp_path / "games"
    secrets = _seed_season(db)
    before = _digest(template)

    code = cli.main(
        ["game", "42", "--db", str(db), "--seed", "7", "--games-dir", str(games)]
    )
    out = capsys.readouterr()
    print(f"exit={code}\nSTDOUT:\n{out.out}\nSTDERR:\n{out.err}")

    assert code == 0
    created = games / "wof001.pptm"
    assert created.exists()
    # stdout names the file and the slot counts...
    assert "wof001.pptm" in out.out
    assert "4 Round" in out.out and "3 Toss-Up" in out.out and "1 Bonus Round" in out.out
    # ...but reveals no solution or category text (spoiler-free).
    combined = out.out + out.err
    leaked = [s for s in secrets if s in combined]
    assert leaked == [], f"operator output leaked: {leaked}"
    # The template is byte-unchanged.
    assert _digest(template) == before


def test_game_second_run_creates_wof002_without_overwriting(template, tmp_path, capsys):
    """Generating twice yields wof001 then wof002; the first file is untouched."""
    db = tmp_path / "store.sqlite"
    games = tmp_path / "games"
    _seed_season(db)

    cli.main(["game", "42", "--db", str(db), "--seed", "7", "--games-dir", str(games)])
    first_digest = _digest(games / "wof001.pptm")
    capsys.readouterr()
    code = cli.main(["game", "42", "--db", str(db), "--seed", "9", "--games-dir", str(games)])
    out = capsys.readouterr()
    print(f"second run exit={code}\n{out.out}")

    assert code == 0
    assert (games / "wof001.pptm").exists()
    assert (games / "wof002.pptm").exists()
    assert _digest(games / "wof001.pptm") == first_digest  # untouched


def test_game_output_is_a_valid_pptm_preserving_vba(template, tmp_path, capsys):
    """The generated file is a valid package whose vbaProject.bin matches the template."""
    db = tmp_path / "store.sqlite"
    games = tmp_path / "games"
    _seed_season(db)
    cli.main(["game", "42", "--db", str(db), "--seed", "7", "--games-dir", str(games)])
    capsys.readouterr()

    with zipfile.ZipFile(template) as tz:
        template_vba = tz.read("ppt/vbaProject.bin")
    with zipfile.ZipFile(games / "wof001.pptm") as gz:
        game_vba = gz.read("ppt/vbaProject.bin")
    print(f"vba sizes template={len(template_vba)} game={len(game_vba)}")
    assert game_vba == template_vba


# --- T016: spoiler-free output, success and error paths (US2) ------------------

def test_success_output_leaks_no_solution_or_category(template, tmp_path, capsys):
    """Full stdout AND stderr of a success contain none of the season's solutions/categories."""
    db = tmp_path / "store.sqlite"
    games = tmp_path / "games"
    secrets = _seed_season(db)  # every solution and category string
    code = cli.main(
        ["game", "42", "--db", str(db), "--seed", "7", "--games-dir", str(games)]
    )
    out = capsys.readouterr()
    combined = out.out + out.err
    print(f"exit={code}\nSTDOUT:\n{out.out}\nSTDERR:\n{out.err}")
    leaked = [s for s in secrets if s in combined]
    assert code == 0
    assert leaked == [], f"operator output leaked puzzle content: {leaked}"


def test_insufficient_type_errors_without_spoilers_or_file(template, tmp_path, capsys):
    """A season short on a type exits 2, names only the type+counts, and writes no file."""
    db = tmp_path / "store.sqlite"
    games = tmp_path / "games"
    # Only 2 Toss-Up puzzles (need 3): an insufficient-type shortfall.
    secrets = _seed_season(db, tossups=2)
    code = cli.main(
        ["game", "42", "--db", str(db), "--seed", "7", "--games-dir", str(games)]
    )
    out = capsys.readouterr()
    print(f"exit={code}\nSTDERR:\n{out.err}")

    assert code == 2
    assert "Toss-Up" in out.err
    assert "need 3" in out.err
    # No puzzle content leaked in the error...
    leaked = [s for s in secrets if s in (out.out + out.err)]
    assert leaked == [], f"error output leaked puzzle content: {leaked}"
    # ...and no game file was written (all-or-nothing).
    assert not (games / "wof001.pptm").exists()


def test_absent_season_errors_cleanly(template, tmp_path, capsys):
    """An absent season exits 2 with a clear, content-free error and no file."""
    db = tmp_path / "store.sqlite"
    games = tmp_path / "games"
    _seed_season(db, season=42)
    code = cli.main(
        ["game", "99", "--db", str(db), "--seed", "7", "--games-dir", str(games)]
    )
    out = capsys.readouterr()
    print(f"exit={code}\nSTDERR:\n{out.err}")
    assert code == 2
    assert "99" in out.err and "not found" in out.err
    assert not (games / "wof001.pptm").exists()

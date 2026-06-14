"""Unit tests for table selection and row parsing (US2).

Runs over the saved fixtures to prove the puzzle table is selected by header
signature (skipping nav/legend tables), rows parse in source order, the header
and empty-PUZZLE rows are skipped, annotation flags are captured, both eras
parse, and a duplicated round label does not collapse two distinct puzzles.
"""

from pathlib import Path

from wheeldb.parser import find_puzzle_table, parse_rows

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _season(name: str, season: int):
    """Load a fixture and parse its puzzle rows.

    Parameters:
        name: fixture file name under tests/fixtures.
        season: season number to attribute to the parsed puzzles.
    Returns:
        The list of parsed ``Puzzle`` objects.
    """
    html = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    table = find_puzzle_table(html)
    return parse_rows(table, season)


def test_finds_puzzle_table_not_legend_or_nav():
    """The selected table is the puzzle table, identified by its header."""
    puzzles = _season("compendium42.html", 42)
    print(f"parsed {len(puzzles)} puzzles from S42 fixture")
    # The legend table has only 2 columns; if it were chosen we'd get nonsense.
    assert all(p.season == 42 for p in puzzles)
    assert {p.round for p in puzzles} & {"T1", "R2", "BR"}


def test_recent_era_first_episode_rows():
    """S42 episode 8011 parses to the three documented puzzles, in order."""
    puzzles = _season("compendium42.html", 42)
    ep = [p for p in puzzles if p.episode == 8011]
    print("episode 8011 puzzles:", [(p.round, p.solution) for p in ep])
    assert [p.round for p in ep] == ["T1", "R2", "BR"]
    assert ep[0].solution == "OPENING NIGHT"  # surrounding quotes stripped
    assert ep[1].solution == "ANIMATED SHORT ATTENTION SPAN"
    assert ep[1].category == "Before & After"  # entity unescaped
    assert ep[1].date == "2024-09-09"


def test_empty_puzzle_row_skipped():
    """A row with an empty PUZZLE cell is not returned as a puzzle."""
    puzzles = _season("compendium42.html", 42)
    ep = [p for p in puzzles if p.episode == 8012]
    rounds = [p.round for p in ep]
    print("episode 8012 rounds (T2 had empty PUZZLE):", rounds)
    assert "T2" not in rounds  # the empty-solution T2 row was skipped
    assert "T1" in rounds


def test_annotation_flags_captured():
    """A prize-puzzle R3* and a trivia R2^ keep clean codes with flags recorded."""
    puzzles = _season("compendium42.html", 42)
    prize = next(p for p in puzzles if p.round == "R3")
    trivia = next(p for p in puzzles if p.round == "R2" and p.episode == 8012)
    print(f"prize flags={prize.flags}; trivia flags={trivia.flags}")
    assert ("round", "*") in prize.flags
    assert ("round", "^") in trivia.flags


def test_early_era_unquoted_and_date_asterisk():
    """S1 rows are unquoted; bicycling date '*' is stripped and flagged."""
    puzzles = _season("compendium1.html", 1)
    first = [p for p in puzzles if p.episode == 1][0]
    print(f"S1 first: solution={first.solution!r}, date={first.date!r}, flags={first.flags}")
    assert first.solution == "BURT LANCASTER"  # was never quoted
    assert first.date == "1983-09-19"
    assert ("date", "*") in first.flags


def test_middle_era_parses():
    """A middle-era season (S20) parses its episode with toss-ups and rounds."""
    puzzles = _season("compendium20.html", 20)
    ep = [p for p in puzzles if p.episode == 3501]
    print("S20 #3501 rounds:", [p.round for p in ep])
    assert [p.round for p in ep] == ["T1", "R1", "R2", "BR"]
    assert ep[0].solution == "HELLO MY NAME IS"
    assert ep[0].date == "2002-09-02"


def test_duplicate_round_label_stays_distinct():
    """Two rows differing only by a duplicated round label remain two puzzles."""
    html = """
    <table>
      <tr><th>PUZZLE</th><th>CATEGORY</th><th>DATE</th><th>EP#</th><th>ROUND</th></tr>
      <tr><td>FIRST ONE</td><td>Thing</td><td>9/9/24</td><td>#8011</td><td>R1</td></tr>
      <tr><td>SECOND ONE</td><td>Thing</td><td>9/9/24</td><td>#8011</td><td>R1</td></tr>
    </table>
    """
    puzzles = parse_rows(find_puzzle_table(html), 42)
    print("duplicate-round puzzles:", [(p.round, p.solution) for p in puzzles])
    assert len(puzzles) == 2
    assert puzzles[0] != puzzles[1]

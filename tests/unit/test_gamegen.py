"""Unit tests for game generation (``wheeldb.gamegen``).

Covers output-file numbering (smallest unused ``wof[N].pptm`` in 1..999, gap reuse,
rollover error), per-type puzzle selection (4 Round / 3 Toss-Up / 1 Bonus, eight
distinct, correct slot ranges), and seeded determinism (FR-012/SC-006). All offline
against a ``tmp_path`` store. On failure tests print the used set / chosen number and
the per-slot selection so a failure is diagnosable (Constitution Principle V).
"""

from __future__ import annotations

import pytest

from wheeldb.errors import GameError
from wheeldb.gamegen import next_game_number, select_puzzles
from wheeldb.models import Puzzle
from wheeldb.storage import PuzzleStore


# --- T008: next_game_number ---------------------------------------------------

def test_empty_dir_yields_one(tmp_path):
    """An empty games dir picks number 1 (-> wof001.pptm)."""
    n = next_game_number(tmp_path)
    print(f"empty dir -> {n}")
    assert n == 1


def test_absent_dir_yields_one(tmp_path):
    """An absent games dir is treated as empty -> number 1 (created later, FR-002)."""
    absent = tmp_path / "does-not-exist"
    n = next_game_number(absent)
    print(f"absent dir -> {n}; exists now: {absent.exists()}")
    assert n == 1


def test_consecutive_used_picks_next(tmp_path):
    """{1,2} used -> 3."""
    (tmp_path / "wof001.pptm").write_bytes(b"")
    (tmp_path / "wof002.pptm").write_bytes(b"")
    n = next_game_number(tmp_path)
    print(f"used {{1,2}} -> {n}")
    assert n == 3


def test_gap_is_reused(tmp_path):
    """{1,3} used -> 2 (smallest unused)."""
    (tmp_path / "wof001.pptm").write_bytes(b"")
    (tmp_path / "wof003.pptm").write_bytes(b"")
    n = next_game_number(tmp_path)
    print(f"used {{1,3}} -> {n}")
    assert n == 2


def test_non_matching_filenames_ignored(tmp_path):
    """Files that don't match wof(\\d{3}).pptm don't perturb numbering."""
    (tmp_path / "wof001.pptm").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    (tmp_path / "wof1.pptm").write_bytes(b"")        # not zero-padded -> ignored
    (tmp_path / "wof001.pptx").write_bytes(b"")      # wrong extension -> ignored
    (tmp_path / "WOF002.PPTM").write_bytes(b"")      # case mismatch -> ignored
    n = next_game_number(tmp_path)
    print(f"used {{1}} (with decoys) -> {n}")
    assert n == 2


def test_all_used_raises(tmp_path):
    """When 1..999 are all used, raise GameError (no silent overwrite)."""
    for i in range(1, 1000):
        (tmp_path / f"wof{i:03d}.pptm").write_bytes(b"")
    with pytest.raises(GameError):
        next_game_number(tmp_path)


# --- T009: select_puzzles -----------------------------------------------------

#: Slot index -> required puzzle type (the fixed SlotPlan; data-model.md).
SLOT_TYPES = {1: "Round", 2: "Round", 3: "Round", 4: "Round",
              5: "Toss-Up", 6: "Toss-Up", 7: "Toss-Up",
              8: "Bonus Round"}


def _season_store(tmp_path, *, rounds=6, tossups=5, bonus=3, season=42):
    """Build a store seeded with a season of puzzles of each type.

    Parameters:
        tmp_path: pytest temp dir for the store file.
        rounds, tossups, bonus: how many of each type to create.
        season: the season number to file them under.
    Returns:
        An open ``PuzzleStore`` (caller closes) seeded with the puzzles.
    """
    store = PuzzleStore(tmp_path / "store.sqlite")
    puzzles = []
    ep = 8000
    for i in range(1, rounds + 1):
        puzzles.append(Puzzle(f"ROUND {i}", "Phrase", "2024-01-01", season, ep, f"R{i}"))
    for i in range(1, tossups + 1):
        puzzles.append(Puzzle(f"TOSSUP {i}", "Thing", "2024-01-01", season, ep, f"T{i}"))
        ep += 1
    for i in range(bonus):
        puzzles.append(Puzzle(f"BONUS {i}", "Place", "2024-01-01", season, ep + i, "BR"))
    with store.transaction():
        for p in puzzles:
            store.upsert(p)
    return store


def test_select_returns_slot_plan_with_correct_types(tmp_path):
    """select_puzzles fills slots 1-4 Round, 5-7 Toss-Up, 8 Bonus, all distinct."""
    store = _season_store(tmp_path)
    plan = select_puzzles(42, store, seed=7)

    print("selected per slot:")
    for slot in range(1, 9):
        p = plan[slot]
        print(f"  slot {slot}: type={p.puzzle_type} key={(p.season, p.episode, p.round)}")

    assert set(plan) == set(range(1, 9))
    for slot, expected in SLOT_TYPES.items():
        assert plan[slot].puzzle_type == expected, f"slot {slot} should be {expected}"
    keys = [(p.season, p.episode, p.round) for p in plan.values()]
    assert len(set(keys)) == 8, "the eight selected puzzles must be distinct"
    store.close()


def test_same_seed_is_deterministic(tmp_path):
    """Same season + same seed -> identical selection (FR-012/SC-006)."""
    store = _season_store(tmp_path)
    a = select_puzzles(42, store, seed=7)
    b = select_puzzles(42, store, seed=7)
    ka = {s: (p.season, p.episode, p.round) for s, p in a.items()}
    kb = {s: (p.season, p.episode, p.round) for s, p in b.items()}
    print(f"selection A: {ka}")
    print(f"selection B: {kb}")
    assert ka == kb
    store.close()


def test_different_seed_may_differ(tmp_path):
    """A different seed can yield a different lineup (selection is actually random)."""
    # Plenty of each type so the sample space is large enough to differ.
    store = _season_store(tmp_path, rounds=20, tossups=20, bonus=10)
    seen = set()
    for seed in range(8):
        plan = select_puzzles(42, store, seed=seed)
        seen.add(tuple((p.season, p.episode, p.round) for p in plan.values()))
    print(f"distinct lineups across 8 seeds: {len(seen)}")
    assert len(seen) > 1
    store.close()


# --- T019: per-type shortfall + absent season error all-or-nothing (US3) -------

@pytest.mark.parametrize(
    "kwargs, short_type, need",
    [
        (dict(rounds=3), "Round", 4),
        (dict(tossups=2), "Toss-Up", 3),
        (dict(bonus=0), "Bonus Round", 1),
    ],
)
def test_insufficient_type_raises_naming_type_and_count(tmp_path, kwargs, short_type, need):
    """Too few of a type raises GameError naming that type and the needed count."""
    store = _season_store(tmp_path, **kwargs)
    by_type: dict[str, int] = {}
    for p in store.puzzles_for_season(42):
        by_type[p.puzzle_type] = by_type.get(p.puzzle_type, 0) + 1
    print(f"per-type availability: {by_type}")
    with pytest.raises(GameError) as ei:
        select_puzzles(42, store, seed=7)
    msg = str(ei.value)
    print(f"error: {msg}")
    assert short_type in msg
    assert f"need {need}" in msg
    store.close()


def test_absent_season_raises_game_error(tmp_path):
    """An absent season raises GameError (no selection possible)."""
    store = _season_store(tmp_path, season=42)
    with pytest.raises(GameError):
        select_puzzles(99, store, seed=7)
    store.close()


# --- T018: type-in-slot read-back from a generated game (US3) ------------------

def test_generated_slots_hold_correct_types(tmp_path):
    """A seeded game's read-back slots match the seeded plan: 1-4 Round, 5-7 Toss-Up, 8 Bonus."""
    import html
    import zipfile
    from pathlib import Path

    from wheeldb.gamegen import generate_game
    from wheeldb.pptx_inject import SLOT_MAPPING

    template = Path(__file__).resolve().parents[2] / "WheelofFortune6.4.pptm"
    if not template.exists():
        pytest.skip("template not present")

    store = _season_store(tmp_path)
    games = tmp_path / "games"
    out = generate_game(42, store=store, games_dir=games, seed=7, template_path=template)
    plan = select_puzzles(42, store, seed=7)  # same seed -> same selection

    with zipfile.ZipFile(out) as zf:
        slide = zf.read(SLOT_MAPPING[1]["slide"]).decode("utf-8")

    def readback(slot):
        import re
        mapping = SLOT_MAPPING[slot]
        text = ""
        for name in mapping["tiles"]:
            for sp in re.findall(r"<p:sp>.*?</p:sp>", slide, re.S):
                m = re.search(r'name="([^"]*)"', sp)
                if m and m.group(1) == name:
                    text += "".join(re.findall(r"<a:t>([^<]*)</a:t>", sp))
        return html.unescape(text)

    for slot in range(1, 9):
        got = readback(slot).replace(" ", "")
        want = plan[slot].solution.replace(" ", "")
        print(f"slot {slot}: type={plan[slot].puzzle_type} got={got!r} want={want!r}")
        assert got == want
    # The eight selected puzzles are distinct.
    keys = {(p.season, p.episode, p.round) for p in plan.values()}
    assert len(keys) == 8
    store.close()

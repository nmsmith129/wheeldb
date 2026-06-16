"""Game generation: season selection, slot assignment, and output numbering.

Glues the puzzle store to the package injector. From a host-named season it selects
four Round, three Toss-Up, and one Bonus Round puzzle (optionally seeded for
reproducibility — FR-012), assigns them to the eight fixed slots (slots 1-4 Round,
5-7 Toss-Up, 8 Bonus Round), picks the smallest unused ``wof[N].pptm`` number, and
writes the game via :func:`wheeldb.pptx_inject.inject_puzzles` — leaving the template
and its VBA untouched. Usable without the CLI and offline (Constitution Principle I);
prints nothing (the CLI owns spoiler-free output — Principle II).
"""

from __future__ import annotations

import os
import random
import re
from pathlib import Path

from wheeldb.errors import GameError
from wheeldb.pptx_inject import inject_puzzles

#: The default template the generator injects into (repo-root macro-enabled file).
DEFAULT_TEMPLATE = Path(__file__).resolve().parents[2] / "WheelofFortune6.4.pptm"

#: Smallest/largest game number (zero-padded to three digits -> wof001..wof999).
_MIN_NUMBER, _MAX_NUMBER = 1, 999

#: Matches exactly ``wof<NNN>.pptm`` (three digits) so non-conforming names are
#: ignored when computing the next number (CHK015 / FR-003).
_GAME_NAME_RE = re.compile(r"^wof(\d{3})\.pptm$")

#: The fixed SlotPlan: each slot range requires one puzzle type (data-model.md).
#: Order matters — selection/validation runs Round, then Toss-Up, then Bonus.
_SLOT_PLAN = (
    ("Round", [1, 2, 3, 4]),
    ("Toss-Up", [5, 6, 7]),
    ("Bonus Round", [8]),
)


def next_game_number(games_dir) -> int:
    """Return the smallest unused game number in 1..999 for a games directory.

    Scans ``games_dir`` for files named exactly ``wof<NNN>.pptm`` and returns the
    smallest integer in 1..999 not already used, so an empty (or absent) directory
    yields 1 and a deleted middle number is reused before later ones (FR-003).

    Parameters:
        games_dir: the output directory (need not exist yet; treated as empty).
    Returns:
        The smallest unused number in 1..999.
    Raises:
        GameError: all 999 numbers are already in use (never overwrites — FR-011).
    """
    used = set()
    try:
        entries = os.listdir(os.fspath(games_dir))
    except FileNotFoundError:
        entries = []
    for name in entries:
        m = _GAME_NAME_RE.match(name)
        if m:
            used.add(int(m.group(1)))
    for n in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if n not in used:
            return n
    raise GameError(
        f"no available wof[N].pptm name in {os.fspath(games_dir)} (001-999 used)"
    )


def game_filename(number: int) -> str:
    """Return the zero-padded game file name for a number (e.g. 1 -> ``wof001.pptm``).

    Parameters:
        number: the game number (1..999).
    Returns:
        The ``wof<NNN>.pptm`` file name.
    """
    return f"wof{number:03d}.pptm"


def _group_by_type(puzzles):
    """Group puzzles by their derived ``puzzle_type``.

    Parameters:
        puzzles: an iterable of ``Puzzle`` objects.
    Returns:
        A dict mapping type name -> list of puzzles of that type.
    """
    groups: dict[str, list] = {}
    for p in puzzles:
        groups.setdefault(p.puzzle_type, []).append(p)
    return groups


def select_puzzles(season, store, seed=None) -> dict[int, object]:
    """Select and assign one puzzle per slot from a season (the SlotPlan).

    Reads the season's puzzles from ``store``, groups them by type, and samples
    without replacement four Round / three Toss-Up / one Bonus Round, assigning them
    to slots 1-4 / 5-7 / 8 respectively. Sampling uses a local ``random.Random`` so
    the same season + same seed yields the identical selection (FR-012/SC-006) and no
    global RNG state is disturbed. Validation runs in the fixed order season-presence
    then per-type counts (FR-015), reporting the first shortfall.

    Parameters:
        season: the season number to draw from.
        store: an open store exposing ``puzzles_for_season(season)``.
        seed: optional integer seed; ``None`` uses system entropy (varies per run).
    Returns:
        A dict mapping each slot index (1..8) to its selected ``Puzzle``; the eight
        puzzles are distinct.
    Raises:
        GameError: the season is absent, or it holds too few puzzles of a type.
    """
    puzzles = store.puzzles_for_season(season)
    if not puzzles:
        raise GameError(f"season {season} not found in store")

    groups = _group_by_type(puzzles)
    rng = random.Random(seed)
    plan: dict[int, object] = {}
    for ptype, slots in _SLOT_PLAN:
        available = groups.get(ptype, [])
        need = len(slots)
        if len(available) < need:
            raise GameError(
                f"season {season} has {len(available)} {ptype} puzzles; need {need}"
            )
        chosen = rng.sample(available, need)
        for slot, puzzle in zip(slots, chosen):
            plan[slot] = puzzle
    return plan


def generate_game(season, *, store, games_dir="games", seed=None,
                  template_path=DEFAULT_TEMPLATE) -> str:
    """Generate one playable game file from a season and return its path.

    Validates in the fixed order (FR-015): template present, season present, per-type
    counts, then number availability — short-circuiting on the first failure with no
    file written (FR-016). On success it selects the SlotPlan, creates ``games_dir``
    if absent (FR-002), picks the smallest unused ``wof[N].pptm`` number, and writes
    the game via the macro-safe injector (template/VBA untouched — FR-004). Prints
    nothing (the CLI owns spoiler-free output).

    Parameters:
        season: the season to draw puzzles from.
        store: an open store exposing ``puzzles_for_season``.
        games_dir: output directory (created if absent); defaults to ``games``.
        seed: optional integer seed for reproducible selection (FR-012).
        template_path: the ``.pptm`` template to inject into.
    Returns:
        The path to the created ``wof[N].pptm`` file.
    Raises:
        GameError: the template is missing, the season is absent or short on a type,
            no number is available, or a slot anchor cannot be located.
    """
    template_path = os.fspath(template_path)
    if not os.path.exists(template_path):
        raise GameError(f"template {template_path} not found")

    # Season presence + per-type counts (raises GameError before any write).
    plan = select_puzzles(season, store, seed=seed)

    games_dir = os.fspath(games_dir)
    os.makedirs(games_dir, exist_ok=True)  # FR-002
    number = next_game_number(games_dir)   # GameError if 001-999 exhausted
    out_path = os.path.join(games_dir, game_filename(number))

    inject_puzzles(template_path, out_path, plan)  # GameError on a missing anchor
    return out_path

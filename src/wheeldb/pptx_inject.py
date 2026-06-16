"""Macro-safe OOXML package editing for game generation.

A ``.pptm`` is an OOXML ZIP. This module is the only place that knows the package
layout: it reads every part from a template, rewrites **only** the slide XML parts
that carry puzzle text, and copies every other entry through **byte-for-byte** — most
importantly ``ppt/vbaProject.bin`` — so the macros and all untouched parts are
identical to the template (Decision 1; FR-004/SC-004). Writes are atomic (temp file
then rename) and never overwrite an existing target. No third-party dependency: the
standard-library ``zipfile`` plus small ``re``-based run edits (Constitution stack).

The slot-injection surface (``inject_puzzles`` + ``SLOT_MAPPING`` and the board
layout) is added on top of this engine.
"""

from __future__ import annotations

import os
import re
import zipfile
from xml.sax.saxutils import escape

from wheeldb.errors import GameError

#: The Wheel of Fortune board: four rows with these column counts, numbered
#: left-to-right then top-to-bottom (tiles 1-12, 13-26, 27-40, 41-52 = 52 total),
#: as captured by the T001 spike (research.md).
BOARD_ROWS = (12, 14, 14, 12)

#: Rows whose first cell is intentionally left blank when placing text (rows are
#: 1-indexed). The spike showed solutions starting at the *second* cell of rows 2/3.
ROWS_SKIP_FIRST_CELL = {2, 3}


def _row_tile_ranges():
    """Return each board row's (start, length) tile offsets (0-based).

    Returns:
        A list of ``(start_index, num_cols)`` per row, in board order.
    """
    ranges = []
    start = 0
    for cols in BOARD_ROWS:
        ranges.append((start, cols))
        start += cols
    return ranges


def lay_out_board(solution: str) -> list[str]:
    """Lay a solution string onto the 52-tile Wheel of Fortune board.

    Reproduces the template's board centering (research.md / T001 spike): words are
    packed onto rows without splitting a word, a single blank tile separates words,
    and placement prefers the vertical middle by starting on **row 2**. Rows 2 and 3
    leave their first cell blank (text starts at the second column), matching the
    captured ``HELLO WORLD`` / ``LET'S A GO`` example. Rows 1 and 4 center their line.

    Parameters:
        solution: the puzzle solution (e.g. ``"HELLO WORLD LET'S A GO"``); case is
            preserved as given (callers pass upper-case board text).
    Returns:
        A list of exactly 52 strings, one per tile (each a single character or the
        empty string for a blank tile), in tile order 1..52.
    Raises:
        GameError: the solution cannot fit the board (too many lines or a single
            word longer than the widest usable row).
    """
    ranges = _row_tile_ranges()
    words = solution.split()
    # Usable width per row (rows 2/3 lose their first cell).
    usable = [cols - (1 if (i + 1) in ROWS_SKIP_FIRST_CELL else 0)
              for i, (_s, cols) in enumerate(ranges)]
    widest = max(usable)
    for w in words:
        if len(w) > widest:
            raise GameError(
                f"puzzle does not fit the board: a word is {len(w)} tiles wide "
                f"(max {widest})"
            )

    # Greedily pack words into lines (a space between words costs one tile).
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= widest:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    # Choose which board rows the lines occupy, preferring to start on row 2 so a
    # short puzzle sits in the vertical middle.
    n = len(lines)
    if n > len(ranges):
        raise GameError(
            f"puzzle does not fit the board: needs {n} lines, board has {len(ranges)}"
        )
    if n == 1:
        row_order = [1]            # single line -> row 2 (0-based index 1)
    elif n == 2:
        row_order = [1, 2]          # two lines -> rows 2 and 3
    elif n == 3:
        row_order = [0, 1, 2]       # three lines -> rows 1-3 (leave row 4 free)
    else:
        row_order = list(range(n))  # four lines -> all rows

    tiles = [""] * sum(BOARD_ROWS)
    for line, row_idx in zip(lines, row_order):
        start, cols = ranges[row_idx]
        skip = 1 if (row_idx + 1) in ROWS_SKIP_FIRST_CELL else 0
        avail = cols - skip
        # Rows that skip their first cell are left-aligned to column 2 (the captured
        # behavior); other rows centre the line within the row.
        if skip:
            offset = skip
        else:
            offset = (avail - len(line)) // 2
        for j, ch in enumerate(line):
            tiles[start + offset + j] = ch
    return tiles


#: The static slot map (T001 spike, named-shape anchors — research.md Decision 4).
#: Each game slot (1..8) records the slide part that holds it, the 52 board-tile
#: shape names that carry one solution character each, and the category shape name.
#: The board cells live on ``ppt/slides/slide12.xml`` as ``PuzzleSolution{slot}-{i}``
#: and ``PuzzleCategory{slot}``; these names are unique and stable, so injection is
#: independent of shape position/order (robust to template edits).
_BOARD_SLIDE = "ppt/slides/slide12.xml"

SLOT_MAPPING = {
    slot: {
        "slide": _BOARD_SLIDE,
        "tiles": [f"PuzzleSolution{slot}-{i}" for i in range(1, 53)],
        "category": f"PuzzleCategory{slot}",
    }
    for slot in range(1, 9)
}


def _set_shape_text(xml: str, shape_name: str, text: str) -> str:
    """Set the run text of one uniquely-named shape within slide XML.

    Locates the ``<p:sp>`` block whose ``p:cNvPr`` name is exactly ``shape_name``,
    then rewrites its first paragraph's run so it contains ``text`` (XML-escaped),
    reusing the paragraph's ``endParaRPr`` formatting as the run properties so the
    injected character keeps the board's font/colour. An empty ``text`` clears the
    run (a blank tile). Only the matched shape is touched; surrounding markup
    (geometry, fill, the VBA-managed styling) is left intact.

    Parameters:
        xml: the decoded slide XML.
        shape_name: the target shape's ``cNvPr`` name (an anchor from SLOT_MAPPING).
        text: the text to place (a single character for a tile, or a category).
    Returns:
        The slide XML with the shape's run text replaced.
    Raises:
        GameError: no shape with ``shape_name`` exists, or it has no text body to
            edit (a missing/renamed anchor — fail loudly, never misplace text).
    """
    sp_pattern = re.compile(
        r'(<p:sp>(?:(?!</p:sp>).)*?name="' + re.escape(shape_name) + r'".*?</p:sp>)',
        re.S,
    )
    m = sp_pattern.search(xml)
    if not m:
        raise GameError(f"puzzle slot anchor not found in template: {shape_name}")
    sp = m.group(1)

    # Find the first paragraph and its endParaRPr (the formatting template).
    para = re.search(r"<a:p>(.*?)</a:p>", sp, re.S)
    if not para:
        raise GameError(f"slot anchor {shape_name} has no paragraph to edit")
    body = para.group(1)

    end = re.search(r"<a:endParaRPr\b[^>]*?(/>|>.*?</a:endParaRPr>)", body, re.S)
    # Derive run properties <a:rPr> from the endParaRPr if present (same attrs/children).
    if end:
        rpr = end.group(0).replace("endParaRPr", "rPr")
    else:
        rpr = '<a:rPr lang="en-US"/>'

    # Drop any existing runs, keep the pPr (alignment) and endParaRPr.
    new_body = re.sub(r"<a:r>.*?</a:r>", "", body, flags=re.S)
    if text:
        run = f"<a:r>{rpr}<a:t>{escape(text)}</a:t></a:r>"
        # Insert the run before endParaRPr (or before </a:p> if none).
        if end:
            idx = new_body.find(end.group(0))
            new_body = new_body[:idx] + run + new_body[idx:]
        else:
            new_body = new_body + run

    new_sp = sp.replace(f"<a:p>{body}</a:p>", f"<a:p>{new_body}</a:p>", 1)
    return xml[: m.start(1)] + new_sp + xml[m.end(1):]


def inject_puzzles(template_path, out_path, slot_assignments) -> None:
    """Write a game package with the assigned puzzles injected into their slots.

    For each ``(slot, Puzzle)`` in ``slot_assignments`` the puzzle's solution is laid
    onto the slot's 52 board tiles (``lay_out_board``) and its category is written to
    the slot's category shape, all on the mapped slide (``SLOT_MAPPING``). Every other
    package part — including ``ppt/vbaProject.bin`` — is preserved byte-for-byte via
    the engine (FR-004). The write is atomic and never overwrites an existing target.
    A missing anchor raises ``GameError`` (no misplaced text, no partial file).

    Parameters:
        template_path: source ``.pptm`` template to inject into.
        out_path: destination path for the generated game (must not exist).
        slot_assignments: mapping of ``{slot_index (1..8): Puzzle}``.
    Raises:
        GameError: the template is unreadable, ``out_path`` exists, a slot index is
            unknown, or a slot anchor cannot be located.
    """
    parts = read_parts(template_path)  # GameError if missing/unreadable

    # Group assignments by slide so each slide part is decoded/edited once.
    by_slide: dict[str, list[tuple[int, object]]] = {}
    for slot, puzzle in slot_assignments.items():
        if slot not in SLOT_MAPPING:
            raise GameError(f"unknown puzzle slot {slot!r} (expected 1..8)")
        by_slide.setdefault(SLOT_MAPPING[slot]["slide"], []).append((slot, puzzle))

    replacements: dict[str, bytes] = {}
    for slide, items in by_slide.items():
        if slide not in parts:
            raise GameError(f"template is missing slide part {slide}")
        xml = parts[slide].decode("utf-8")
        for slot, puzzle in items:
            mapping = SLOT_MAPPING[slot]
            tiles = lay_out_board(puzzle.solution)
            for shape_name, ch in zip(mapping["tiles"], tiles):
                xml = _set_shape_text(xml, shape_name, ch)
            xml = _set_shape_text(xml, mapping["category"], puzzle.category)
        replacements[slide] = xml.encode("utf-8")

    write_package(template_path, out_path, replacements)


def read_parts(template_path) -> dict[str, bytes]:
    """Read every part of a ``.pptm`` package into a name -> bytes mapping.

    Parameters:
        template_path: filesystem path to the source ``.pptm`` package.
    Returns:
        An insertion-ordered dict mapping each archive member name to its raw,
        decompressed bytes, in the package's original entry order.
    Raises:
        GameError: the template is missing, unreadable, or not a valid ZIP/OOXML
            package.
    """
    try:
        with zipfile.ZipFile(os.fspath(template_path)) as zf:
            return {name: zf.read(name) for name in zf.namelist()}
    except FileNotFoundError as exc:
        raise GameError(f"template {os.fspath(template_path)} not found") from exc
    except (OSError, zipfile.BadZipFile) as exc:
        raise GameError(
            f"could not read template package {os.fspath(template_path)}: {exc}"
        ) from exc


def write_package(template_path, out_path, replacements) -> None:
    """Write a new package from a template, rewriting only the named parts.

    Reads all parts from ``template_path``, substitutes the bytes of any part named
    in ``replacements``, and copies every other entry through unchanged so the VBA
    project and untouched slides stay byte-identical (FR-004). The output is written
    to a sibling temp file and atomically renamed into place, so a failure leaves no
    partial file. Refuses to overwrite an existing ``out_path``.

    Parameters:
        template_path: source ``.pptm`` package to copy from.
        out_path: destination path; must not already exist.
        replacements: mapping of ``{part_name: new_bytes}`` for the parts to
            rewrite (every other part is preserved exactly). ``new_bytes`` must be
            ``bytes``/``bytearray``.
    Raises:
        GameError: the template is unreadable, ``out_path`` already exists, or the
            write fails.
        TypeError: a replacement value is not ``bytes``/``bytearray`` (a caller
            programming error; surfaced before any output file is created).
    """
    out_path = os.fspath(out_path)
    if os.path.exists(out_path):
        raise GameError(f"refusing to overwrite existing file {out_path}")

    for name, value in replacements.items():
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(
                f"replacement for part {name!r} must be bytes, got {type(value).__name__}"
            )

    parts = read_parts(template_path)  # may raise GameError (missing/unreadable)
    unknown = set(replacements) - set(parts)
    if unknown:
        raise GameError(
            f"cannot rewrite parts absent from the template: {sorted(unknown)}"
        )

    tmp_path = f"{out_path}.tmp"
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in parts.items():
                zf.writestr(name, replacements.get(name, data))
        os.replace(tmp_path, out_path)
    except OSError as exc:
        raise GameError(f"could not write package {out_path}: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

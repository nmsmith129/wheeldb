"""Unit tests for the macro-safe OOXML package engine (``wheeldb.pptx_inject``).

The engine reads a ``.pptm`` package, rewrites only named parts, and copies every
other entry through byte-for-byte — most importantly ``ppt/vbaProject.bin`` — so the
macros and untouched slides are identical to the template (FR-004/SC-004). Writes are
atomic (no partial file on error) and never overwrite an existing target. Tests run
offline against the disposable ``template_pptm`` fixture; on failure they print the
list of parts that differ so a regression is diagnosable (Constitution Principle V).
"""

from __future__ import annotations

import zipfile

import pytest

from wheeldb.errors import GameError
from wheeldb.pptx_inject import read_parts, write_package


def _entries(path):
    """Return ``{name: bytes}`` for every entry in a ZIP package.

    Parameters:
        path: filesystem path to the ``.pptm``/zip file.
    Returns:
        A dict mapping each archive member name to its raw bytes.
    """
    with zipfile.ZipFile(path) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _diff_names(a, b):
    """Return the sorted names whose bytes differ (or are missing) between two maps.

    Parameters:
        a, b: ``{name: bytes}`` mappings to compare.
    Returns:
        Sorted list of names present-and-different or present-in-one-only.
    """
    names = set(a) | set(b)
    return sorted(n for n in names if a.get(n) != b.get(n))


def test_round_trip_preserves_every_part(template_pptm, tmp_path):
    """Rewriting a package with no replacements yields a byte-identical copy."""
    out = tmp_path / "copy.pptm"
    write_package(template_pptm, out, {})

    src, dst = _entries(template_pptm), _entries(out)
    print(f"parts in template: {len(src)}; parts in output: {len(dst)}")
    print(f"differing parts: {_diff_names(src, dst)}")

    assert set(src) == set(dst)
    assert _diff_names(src, dst) == []


def test_rewriting_one_part_leaves_all_others_byte_identical(template_pptm, tmp_path):
    """Replacing a single slide part changes only that part; VBA and others are intact."""
    src = _entries(template_pptm)
    target = "ppt/slides/slide12.xml"
    assert target in src, "fixture is missing the expected slide part"
    new_bytes = src[target].replace(b"<a:t>", b"<a:t>", 1)  # identical-length sentinel edit
    new_bytes = new_bytes + b"<!-- edited -->"

    out = tmp_path / "edited.pptm"
    write_package(template_pptm, out, {target: new_bytes})

    dst = _entries(out)
    differing = _diff_names(src, dst)
    print(f"differing parts after one-part rewrite: {differing}")
    print(f"vbaProject identical: {src['ppt/vbaProject.bin'] == dst['ppt/vbaProject.bin']}")

    assert differing == [target]
    assert dst[target] == new_bytes
    assert dst["ppt/vbaProject.bin"] == src["ppt/vbaProject.bin"]


def test_read_parts_returns_named_bytes(template_pptm):
    """read_parts exposes each part's bytes keyed by archive name."""
    parts = read_parts(template_pptm)
    print(f"read {len(parts)} parts; has vbaProject: {'ppt/vbaProject.bin' in parts}")
    assert "ppt/vbaProject.bin" in parts
    assert "ppt/slides/slide12.xml" in parts
    assert isinstance(parts["ppt/slides/slide12.xml"], (bytes, bytearray))


def test_write_refuses_to_overwrite_existing_target(template_pptm, tmp_path):
    """Writing to a path that already exists raises GameError and leaves it untouched."""
    out = tmp_path / "exists.pptm"
    out.write_bytes(b"original")
    with pytest.raises(GameError):
        write_package(template_pptm, out, {})
    print(f"target bytes after refused write: {out.read_bytes()!r}")
    assert out.read_bytes() == b"original"


def test_failed_write_leaves_no_partial_file(template_pptm, tmp_path):
    """If a replacement value is invalid, no output file is left behind (atomic write)."""
    out = tmp_path / "partial.pptm"
    # A non-bytes replacement value forces a failure mid-write.
    with pytest.raises((GameError, TypeError, ValueError)):
        write_package(template_pptm, out, {"ppt/slides/slide12.xml": object()})
    print(f"output exists after failed write: {out.exists()}")
    assert not out.exists()


def test_missing_template_raises_game_error(tmp_path):
    """Reading from an absent template path raises GameError."""
    missing = tmp_path / "nope.pptm"
    with pytest.raises(GameError):
        write_package(missing, tmp_path / "out.pptm", {})


# --- T010: inject_puzzles + SLOT_MAPPING + board layout -----------------------

import re  # noqa: E402  (test-local helper imports)

from wheeldb.models import Puzzle  # noqa: E402
from wheeldb.pptx_inject import SLOT_MAPPING, inject_puzzles, lay_out_board  # noqa: E402


def _shape_text(xml: str, shape_name: str) -> str:
    """Return the concatenated <a:t> text of one uniquely-named shape in slide XML.

    Parameters:
        xml: decoded slide XML.
        shape_name: the ``p:cNvPr`` name to locate.
    Returns:
        The shape's run text joined (empty string if the shape has no text run).
    """
    # Match the <p:sp> block whose cNvPr name is exactly shape_name.
    for sp in re.findall(r"<p:sp>.*?</p:sp>", xml, re.S):
        m = re.search(r'name="([^"]*)"', sp)
        if m and m.group(1) == shape_name:
            return "".join(re.findall(r"<a:t>([^<]*)</a:t>", sp))
    return None  # shape not found


def _readback_slot(out_path, slot: int):
    """Read back a slot's 52 tiles + category text from the generated package.

    Parameters:
        out_path: path to the generated ``.pptm``.
        slot: game slot index (1..8).
    Returns:
        ``(tiles, category)`` where ``tiles`` is a list of 52 strings.
    """
    mapping = SLOT_MAPPING[slot]
    with zipfile.ZipFile(out_path) as zf:
        xml = zf.read(mapping["slide"]).decode("utf-8")
    import html
    tiles = [html.unescape(_shape_text(xml, name) or "") for name in mapping["tiles"]]
    category = html.unescape(_shape_text(xml, mapping["category"]) or "")
    return tiles, category


def _shape_fill(xml: str, shape_name: str) -> str:
    """Return the shape-fill hex (first ``a:srgbClr`` value) of one named shape.

    The tile's shape fill is the first ``<a:solidFill><a:srgbClr val="…"/>`` in its
    ``<p:sp>`` (before the ``<a:ln>`` line colour), so the first ``srgbClr`` match is
    the tile colour: ``FFFFFF`` (white, lettered) or ``189A50`` (green, blank).

    Parameters:
        xml: decoded slide XML.
        shape_name: the ``p:cNvPr`` name to locate.
    Returns:
        The upper-cased 6-hex fill value, or ``None`` if the shape/fill is absent.
    """
    for sp in re.findall(r"<p:sp>.*?</p:sp>", xml, re.S):
        m = re.search(r'name="([^"]*)"', sp)
        if m and m.group(1) == shape_name:
            vals = re.findall(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', sp)
            return vals[0].upper() if vals else None
    return None


def _readback_fills(out_path, slot: int):
    """Read back the 52 tile shape-fill hex values for a slot (one per tile).

    Parameters:
        out_path: path to the generated ``.pptm``.
        slot: game slot index (1..8).
    Returns:
        A list of 52 upper-cased hex strings in tile order 1..52.
    """
    mapping = SLOT_MAPPING[slot]
    with zipfile.ZipFile(out_path) as zf:
        xml = zf.read(mapping["slide"]).decode("utf-8")
    return [_shape_fill(xml, name) for name in mapping["tiles"]]


def _assignments(**by_slot):
    """Build a slot->Puzzle assignment dict for the given slots.

    Parameters:
        by_slot: ``slotN=Puzzle`` keyword args (e.g. slot1=..., slot8=...).
    Returns:
        ``{int: Puzzle}`` ready for inject_puzzles.
    """
    return {int(k.replace("slot", "")): v for k, v in by_slot.items()}


def test_slot_mapping_covers_eight_slots_with_52_tiles_each():
    """SLOT_MAPPING has all 8 slots, each with a slide, 52 tiles, and a category anchor."""
    assert set(SLOT_MAPPING) == set(range(1, 9))
    for slot, m in SLOT_MAPPING.items():
        assert len(m["tiles"]) == 52, f"slot {slot} must have 52 tile anchors"
        assert m["category"]
        assert m["slide"].startswith("ppt/slides/")


def test_board_layout_matches_the_spike_example():
    """HELLO WORLD / LET'S A GO lays out exactly as the human spike captured it.

    The captured ground truth: row 2 (tiles 13-26) holds HELLO WORLD starting at
    tile 14 (the 2nd cell), and row 3 (tiles 27-40) holds LET'S A GO starting at
    tile 28 (the 2nd cell). Board rows are [12, 14, 14, 12] tiles.
    """
    tiles = lay_out_board("HELLO WORLD LET'S A GO")
    placed = {i + 1: ch for i, ch in enumerate(tiles) if ch}
    print(f"placed tiles: {placed}")
    assert len(tiles) == 52
    # Row 2 (tiles 13-26) holds the first line starting at the 2nd cell (tile 14).
    assert "".join(tiles[13:24]) == "HELLO WORLD"   # tiles 14..24 (0-based 13..23)
    # Row 3 (tiles 27-40) holds the second line starting at the 2nd cell (tile 28).
    assert "".join(tiles[27:37]) == "LET'S A GO"     # tiles 28..37 (0-based 27..36)
    # The unused first cells of rows 2 and 3 stay blank.
    assert tiles[12] == ""   # tile 13
    assert tiles[26] == ""   # tile 27


def test_start_row_depends_on_length_not_line_count():
    """Row 2 starts puzzles of length 1-24; row 1 starts puzzles of length 25+.

    Length is the sum of the stripped wrapped-row lengths. A short puzzle begins on
    row 2 (tiles 13-26); a longer one begins on row 1 (tiles 1-12).
    """
    # Three short words wrap to 3 lines but sum to length 21 (<= 24); the length rule
    # puts them on row 2 (rows 2-4), unlike a line-count rule that would start on row 1.
    short = lay_out_board("ABCDEFG HIJKLMN OPQRSTU")  # length 21 -> row 2
    short_first = next(i for i, ch in enumerate(short) if ch)
    print(f"short first tile (0-based): {short_first}")
    assert all(ch == "" for ch in short[0:12])         # row 1 empty
    assert 12 <= short_first <= 25                      # first letter on row 2

    long = lay_out_board("WHEEL OF FORTUNE BONUS ROUND PUZZLE")  # length 32 -> row 1
    long_first = next(i for i, ch in enumerate(long) if ch)
    print(f"long first tile (0-based): {long_first}")
    assert 0 <= long_first <= 11                        # first letter on row 1


def test_all_rows_are_left_aligned():
    """Every row is left-aligned to its leftmost usable tile (no centering).

    For a 4-line puzzle, row 1 begins at tile 1 and row 4 begins at tile 41.
    """
    tiles = lay_out_board("WHEEL OF FORTUNE BONUS ROUND PUZZLE")
    print(f"row1 head={tiles[0:8]!r} row4 head={tiles[40:46]!r}")
    assert tiles[0] == "W"     # row 1, tile 1 (left edge), not centered
    assert tiles[40] == "P"    # row 4, tile 41 (left edge), not centered


def test_first_and_last_cells_of_rows_2_3_only_used_over_48():
    """Rows 2/3 use their first/last cell only when the puzzle length exceeds 48."""
    # length 49 -> expanded: rows 2/3 use their first cell (tiles 13 and 27).
    expanded = lay_out_board("BIG MONEY ON THE WHEEL OF FORTUNE COMES AROUND TODAY")
    print(f"tile13={expanded[12]!r} tile27={expanded[26]!r}")
    assert expanded[12] != ""   # tile 13 (row 2 first cell) is used
    assert expanded[26] != ""   # tile 27 (row 3 first cell) is used

    # length 48 -> not expanded: the first/last cells of rows 2/3 stay blank.
    inset = lay_out_board("ABCDEFGHIJKL MNOPQRSTUVWX YZABCDEFGHIJ KLMNOPQRSTUV")
    print(f"inset corners: {[inset[i] for i in (12, 25, 26, 39)]!r}")
    assert inset[12] == ""      # tile 13  (row 2 first cell)
    assert inset[25] == ""      # tile 26  (row 2 last cell)
    assert inset[26] == ""      # tile 27  (row 3 first cell)
    assert inset[39] == ""      # tile 40  (row 3 last cell)


def test_inject_colors_lettered_tiles_white_and_blanks_green(template_pptm, tmp_path):
    """Lettered tiles read back white (FFFFFF); blanks read back green (189A50).

    Injecting a *shorter* puzzle into slot 1 (which ships a baked-in sample puzzle)
    must also reset the sample's stale white tiles back to green.
    """
    out = tmp_path / "colored.pptm"
    p = Puzzle("GO", "Phrase", "2024-01-01", 42, 8000, "R1")  # only tiles 14,15 lettered
    inject_puzzles(template_pptm, out, _assignments(slot1=p))

    tiles, _ = _readback_slot(out, 1)
    fills = _readback_fills(out, 1)
    print(f"lettered tiles: {[i + 1 for i, t in enumerate(tiles) if t]}")
    print(f"tile14 fill={fills[13]} tile16 fill(was sample 'L')={fills[15]}")

    for i, (ch, fill) in enumerate(zip(tiles, fills)):
        if ch:
            assert fill == "FFFFFF", f"tile {i + 1} ({ch!r}) should be white, got {fill}"
        else:
            assert fill == "189A50", f"tile {i + 1} (blank) should be green, got {fill}"


def test_inject_writes_assigned_text_into_mapped_slots(template_pptm, tmp_path):
    """After injection, each slot's tiles read back as the assigned solution + category."""
    out = tmp_path / "game.pptm"
    p1 = Puzzle("HELLO WORLD LET'S A GO", "Phrase", "2024-01-01", 42, 8000, "R1")
    p8 = Puzzle("GRAND PRIZE", "Award", "2024-01-01", 42, 8007, "BR")
    inject_puzzles(template_pptm, out, _assignments(slot1=p1, slot8=p8))

    tiles1, cat1 = _readback_slot(out, 1)
    tiles8, cat8 = _readback_slot(out, 8)
    print(f"slot1 nonblank: {[t for t in tiles1 if t]}  category={cat1!r}")
    print(f"slot8 nonblank: {[t for t in tiles8 if t]}  category={cat8!r}")

    assert "".join(tiles1[13:24]) == "HELLO WORLD"
    assert "".join(tiles1[27:37]) == "LET'S A GO"
    assert cat1 == "Phrase"
    assert "".join(t for t in tiles8 if t).replace(" ", "") == "GRANDPRIZE".replace(" ", "")
    assert cat8 == "Award"


def test_inject_xml_escapes_special_characters(template_pptm, tmp_path):
    """Solutions/categories with & < > and quotes round-trip correctly (XML-escaped)."""
    out = tmp_path / "special.pptm"
    p = Puzzle("TOM & JERRY", 'A "B" <C>', "2024-01-01", 42, 8000, "R1")
    inject_puzzles(template_pptm, out, _assignments(slot1=p))

    tiles, cat = _readback_slot(out, 1)
    joined = "".join(tiles)
    print(f"slot1 letters joined: {joined!r}; category={cat!r}")
    assert "&" in joined          # the ampersand survived as a literal character
    assert cat == 'A "B" <C>'
    # The written XML must be well-formed (escaped), not raw '&'.
    with zipfile.ZipFile(out) as zf:
        raw = zf.read(SLOT_MAPPING[1]["slide"]).decode("utf-8")
    assert "<a:t>&</a:t>" not in raw   # a bare & would be invalid XML
    assert "&amp;" in raw


def test_inject_preserves_vba_and_untouched_parts(template_pptm, tmp_path):
    """Injection rewrites only slide parts carrying slots; VBA + others stay identical."""
    out = tmp_path / "preserve.pptm"
    p = Puzzle("HELLO WORLD", "Phrase", "2024-01-01", 42, 8000, "R1")
    inject_puzzles(template_pptm, out, _assignments(slot1=p))

    src, dst = _entries(template_pptm), _entries(out)
    differing = _diff_names(src, dst)
    print(f"parts changed by injection: {differing}")
    assert "ppt/vbaProject.bin" not in differing
    assert dst["ppt/vbaProject.bin"] == src["ppt/vbaProject.bin"]
    # Only slide parts are touched.
    assert all(d.startswith("ppt/slides/slide") for d in differing)


def test_inject_missing_anchor_raises_game_error(template_pptm, tmp_path):
    """A SLOT_MAPPING entry whose anchor is absent raises GameError, not misplacement."""
    # Corrupt the in-memory mapping for slot 1 to reference a non-existent shape.
    import copy
    saved = copy.deepcopy(SLOT_MAPPING[1])
    try:
        SLOT_MAPPING[1]["tiles"][0] = "NoSuchShapeXYZ"
        out = tmp_path / "bad.pptm"
        p = Puzzle("HELLO", "X", "2024-01-01", 42, 8000, "R1")
        with pytest.raises(GameError):
            inject_puzzles(template_pptm, out, _assignments(slot1=p))
        print(f"output exists after missing-anchor failure: {out.exists()}")
        assert not out.exists()
    finally:
        SLOT_MAPPING[1].clear()
        SLOT_MAPPING[1].update(saved)


def test_inject_survives_unrelated_added_part(template_pptm, tmp_path):
    """An unrelated added part (simulating a user edit) survives injection byte-for-byte."""
    # Add an extra benign part to a copy of the template (a user customization).
    edited = tmp_path / "edited_template.pptm"
    extra_name = "ppt/media/userwedge.bin"
    extra_bytes = b"USER WHEEL WEDGE CUSTOMIZATION"
    write_package(template_pptm, edited, {})  # plain copy
    # Append the extra part.
    with zipfile.ZipFile(edited, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(extra_name, extra_bytes)

    out = tmp_path / "game.pptm"
    p = Puzzle("HELLO WORLD", "Phrase", "2024-01-01", 42, 8000, "R1")
    inject_puzzles(edited, out, _assignments(slot1=p))

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        survived = zf.read(extra_name) if extra_name in names else None
    print(f"added part present in output: {extra_name in names}")
    assert extra_name in names
    assert survived == extra_bytes

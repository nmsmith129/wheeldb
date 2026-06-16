# Injector Contract: `pptx_inject`

`pptx_inject` is the only module that knows the OOXML package layout. It reads the
template, writes puzzle text into the eight slots, and saves a new package while
preserving every untouched part byte-for-byte (Constitution I; FR-004).

## Public surface

| Function | Contract |
|----------|----------|
| `inject_puzzles(template_path, out_path, slot_assignments)` | Read the template package; for each slot in `slot_assignments` (slot index → `Puzzle`), set the slot's **solution** and **category** text in the mapped slide XML run; copy all other parts (incl. `ppt/vbaProject.bin`) through unchanged; write `out_path` atomically (temp file then rename) and never overwrite an existing `out_path`. Raises `GameError` if the template is missing/unreadable or a mapped slot/run is not found. |
| `SLOT_MAPPING` | Static table (slot index → **stable anchor** for the solution run and the category run), captured by the spike (research Decision 4). Anchors are content placeholder tokens (preferred, e.g. `{{PUZZLE_1_SOLUTION}}`) or unique `(slide part, shape name)` pairs — **never positional indices**. The single source of truth for where text is written. |

## Guarantees (testable offline)

- **Macro & part preservation**: in the output package, every part except the edited
  slide XML parts is byte-identical to the template — verified by comparing each
  ZIP entry's bytes; `ppt/vbaProject.bin` in particular is unchanged (FR-004/SC-004).
- **Slot fidelity**: re-reading the output package's mapped runs yields exactly the
  injected solution/category text, including special characters (round-trip).
- **No partial output**: on any error, no `out_path` is left behind (atomic write).
- **No overwrite**: `inject_puzzles` refuses to write if `out_path` already exists
  (the caller supplies a pre-validated unused name).
- **Robust to template customization**: because slots are located by stable anchors
  (not position) and every non-slot part is copied through unchanged, a user editing
  the template elsewhere (e.g. adding a wheel wedge) or re-saving it in PowerPoint
  does not move the slots, and the customization is preserved in the output. If an
  anchor is genuinely gone (a slot shape removed/renamed), the run raises `GameError`
  rather than misplacing a puzzle.

## Notes

- XML edits target only the runs resolved via each slot's anchor in `SLOT_MAPPING`
  (replacing a placeholder token's text, or the text of a uniquely named shape's run);
  surrounding slide markup is left intact so the board/layout the VBA expects is
  unchanged.
- Text is XML-escaped on write so solutions/categories containing `&`, `<`, `>`, or
  quotes round-trip correctly.

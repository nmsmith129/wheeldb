# Phase 0 Research: PowerPoint Puzzle Injection

The spec is clarified (season-scoped random selection, optional seed). The decisions
below resolve the technical unknowns — chiefly how to edit a macro-enabled package
without breaking it, and how to locate the eight puzzle slots.

## Decision 1 — Macro-safe package editing (no python-pptx)

- **Decision**: Treat the `.pptm` as an OOXML ZIP and edit it with the standard
  library `zipfile`. Read every part from the template, rewrite **only** the slide
  XML parts whose puzzle slots change, and copy every other part (most importantly
  `ppt/vbaProject.bin`, plus `[Content_Types].xml`, rels, media, etc.) through
  **byte-for-byte**. Preserve each entry's name and compression so the macro project
  and all untouched parts are identical to the template.
- **Rationale**: FR-004/SC-004 require the macros to remain intact. `python-pptx` is
  not installed, is not a project dependency, and does not safely round-trip
  macro-enabled packages (it can drop or rewrite the VBA part and re-serialize XML).
  Raw `zipfile` editing is dependency-free (Constitution stack stays stdlib + the
  existing scraping deps) and lets us guarantee byte-equality of untouched parts,
  which is directly testable. *(Resolves the python-pptx question; supports
  CHK on package integrity.)*
- **Alternatives considered**: `python-pptx` (rejected — macro round-trip risk, new
  dep, not installed); editing via COM/PowerPoint automation (rejected — not
  offline, Windows-PowerPoint-only, untestable in CI); shelling out to a converter
  (rejected — heavyweight, non-deterministic).

## Decision 2 — Selecting puzzles from the store by season and type

- **Decision**: Add one read query to the store, `puzzles_for_season(season) ->
  list[Puzzle]`, returning that season's puzzles as `Puzzle` objects (reusing the
  existing row→Puzzle shape). `gamegen` groups them by `puzzle_type` (`Round`,
  `Toss-Up`, `Bonus Round`) using the model's existing derivation, then samples four
  / three / one without replacement per type.
- **Rationale**: Reuse over creation (Principle IV) — the store already owns data
  access; a single typed query avoids a parallel data path. Grouping by the model's
  `puzzle_type` keeps the type taxonomy in one place. Per-type sampling without
  replacement satisfies the distinctness requirement (FR-007).
- **Alternatives considered**: reading the store file directly from `gamegen`
  (rejected — duplicates storage knowledge); adding a type-filtered SQL query per
  type (reasonable, but one season query + in-memory grouping is simpler and would
  generalize to the CSV store if feature 005 is later brought into scope).

## Decision 3 — Output file numbering

- **Decision**: Scan the `games/` folder for names matching exactly `wof(\d{3})\.pptm`,
  collect the used numbers, and pick the smallest value in `1..999` not present;
  format zero-padded to three digits (`wof001.pptm` … `wof999.pptm`), so an empty
  folder yields `wof001.pptm` (matching spec US1 acceptance scenario 1). Create
  `games/` if absent. If all 999 numbers are used, raise `GameError`. Non-matching
  filenames are ignored when computing the next number.
- **Rationale**: Directly implements FR-003/FR-011 and the gap-reuse edge case
  (a deleted `wof001.pptm` is reused before `wof003.pptm`). Anchoring the regex to
  the exact pattern (CHK015) prevents stray files from perturbing numbering.
- **Alternatives considered**: a monotonic counter file (rejected — drifts from the
  actual directory contents, can overwrite after deletion); `max+1` (rejected —
  doesn't reuse gaps as the spec requires).

## Decision 4 — Locating the eight puzzle slots: stable anchors, not positions [SPIKE]

- **Decision**: Each slot's **solution** and **category** text is located by a
  **stable, edit-resistant anchor** — never by a positional index. A one-time spike
  (done by a human with PowerPoint) chooses the anchoring flavor and captures the
  mapping into `pptx_inject.SLOT_MAPPING`:
  1. **Preferred — content placeholder tokens**: prep the template once so each slot
     contains a unique sentinel string in its solution and category runs (e.g.
     `{{PUZZLE_1_SOLUTION}}` / `{{PUZZLE_1_CATEGORY}}` … through slot 8). The injector
     finds and replaces these tokens. `SLOT_MAPPING` is just the token list; the
     locator is the token text itself. This is the robust default.
  2. **Conditional — named-shape anchor**: if the spike finds the eight slot shapes
     already have unique, stable shape names, locate by `(slide part, shape name)`
     instead, with no template prep. Use this only when the names are genuinely
     unique and stable.
  3. **Rejected — positional/index locators** (e.g. "the 5th `<a:t>` on slide 12"):
     brittle — broken by shape reordering, slide moves, or PowerPoint rewriting the
     package on save.
  Spike procedure: enter unique sentinels per slot in PowerPoint, save, unzip and
  diff `ppt/slides/*.xml` to confirm where each sentinel lands and whether the
  containing shape is uniquely named; record the chosen anchors as data.
- **Robustness to template edits (answers the "add a prize wedge" question)**: anchors
  make injection independent of position/order, so a user customizing the template
  (e.g. adding a wedge to the wheel, restyling, reordering slides) — and PowerPoint
  re-saving it — does **not** move the slots. Because every non-slot part is copied
  through byte-for-byte (Decision 1), the user's customization rides into every
  generated game unchanged. Token anchors specifically survive PowerPoint's
  structural rewrites because text content is preserved even when XML is reordered.
- **Backstop, not primary mechanism**: `inject_puzzles` MUST raise `GameError` if any
  slot's anchor cannot be found, so a template change that truly removes/renames a
  slot fails loudly rather than misplacing a puzzle (injector-contract.md). Re-running
  the spike is advised only when the slots themselves are edited — not for unrelated
  changes like a wheel wedge.
- **Rationale**: The template ships with **empty** slots and the puzzle text is not in
  obviously-named shapes, so a robust locator cannot be assumed from static
  inspection. Content tokens are the most resilient option (independent of the
  template's internal naming and of PowerPoint re-saves) at the cost of a one-time,
  benign template prep that touches no VBA.
- **Testability**: Once `SLOT_MAPPING` exists (token list or names), injection is fully
  testable offline by replacing the tokens / named runs and re-reading them — no
  PowerPoint needed in CI.
- **Alternatives considered**: positional indices (rejected — brittle, see above);
  parsing the VBA to learn how it reads slots (rejected — `vbaProject.bin` is
  OVBA-compressed; far more effort, and we must not modify it).
- **Open dependency**: this spike is the first implementation step; until the anchors
  are captured (and, for the token flavor, the prepped template committed), the
  injection tasks are blocked. It does not change the spec or the architecture above.

### Spike findings (2026-06-15, static inspection of `WheelofFortune6.4.pptm`)

Static unzip + `ppt/slides/*.xml` inspection (no PowerPoint) established the
template's puzzle storage layout, and — importantly — established that the **anchor
choice cannot be finalized by static inspection alone** because the solution is not
stored as a single text run anywhere in the package:

- **Shapes are uniquely named** (good news for the named-anchor flavor). The puzzle
  data shapes carry stable, unique names:
  - `ppt/slides/slide8.xml` — the "Set Up Puzzles" editing surface. Holds **one
    puzzle at a time** as 52 single-letter tiles `SetUpPuzzle1` … `SetUpPuzzle52`
    (each `<a:t>` is one letter) plus one `SetUpPuzzleCategory` shape. A row selector
    (`NextPuzzleRow`/`PrevPuzzleRow`, with `CurrentPuzzleRowIndex` = `0` on slide 7)
    pages through the puzzles; the visible tiles are whichever row is selected.
  - `ppt/slides/slide12.xml` — per-puzzle board cells `PuzzleSolution{N}-{1..52}` and
    `PuzzleCategory{N}` for **N = 1..12** (the template supports up to 12 puzzles).
    Shipped **empty**.
  - `ppt/slides/slide2.xml` — `PuzzleCache1` … `PuzzleCache52`, `PuzzleBoard1..52`,
    plus round-type labels. Shipped empty.
  - `ppt/slides/slide9.xml` — `PuzzleSolutionSwap-{1..52}`, `PuzzleCategorySwap`.
- **The solution is stored only as per-letter tiles**, never as a single solution
  string run. A whole-package text search for any multi-word solution string
  (e.g. the demo "HELLO WORLD") found nothing; the demo solution exists only as the
  individual `SetUpPuzzle*` letter tiles. So "set the solution run" is **not** a
  single-run edit — injecting a puzzle means writing one letter per tile across 52
  tiles, matching exactly how the VBA reads/loads a row, including blank tiles for
  spaces and tile-skips for word breaks.
- **`ppt/vbaProject.bin`** is 232,448 bytes and must be copied through byte-for-byte
  (Decision 1) — and we must NOT parse/modify it (Decision 4 rejected this).

**Resolved by a human-run spike (2026-06-15).** The user entered a known puzzle —
solution `HELLO WORLD` / `LET'S A GO` — into slot 1 in PowerPoint and saved. Diffing
the resulting slide XML resolved the encoding:

- **Board geometry**: the 52 tiles form the standard Wheel of Fortune board of **4
  rows with column counts `[12, 14, 14, 12]`**, numbered left-to-right then
  top-to-bottom:
  - Row 1 → tiles 1–12 (12 columns)
  - Row 2 → tiles 13–26 (14 columns)
  - Row 3 → tiles 27–40 (14 columns)
  - Row 4 → tiles 41–52 (12 columns)
- **Per-tile encoding**: each character of the solution occupies one tile (`<a:t>` =
  one character); blank tiles are gaps (spaces, line padding, the unused edge cells).
  The same content is written to **both** `slide8` `SetUpPuzzle{1..52}` and `slide12`
  `PuzzleSolution1-{1..52}`.
- **Observed placement**: `HELLO WORLD` (11 chars) landed on **Row 2** at tiles
  **14–24** — i.e. starting at the *second* cell of row 2 (tile 13 left blank).
  `LET'S A GO` (9 chars) landed on **Row 3** at tiles **28–36** — again starting at
  the second cell (tile 27 left blank). The puzzle began on row 2, not row 1.

**Layout rule to implement (per the user's direction).** A WoF board-centering
layout that (a) prefers starting on **row 2** (so short puzzles sit in the vertical
middle), and (b) **does not use the first cell of rows 2 and 3** — each word/line is
placed so the leftmost used cell of rows 2/3 is column 2 or later. Words wrap across
rows without splitting a word; spaces between words consume one blank tile. This is a
best-effort reproduction of the template's centering; correctness of *play* is to be
confirmed by opening a generated file in PowerPoint (the artifact-level check), while
offline tests assert the tiles round-trip to the intended characters.

- **Category**: left empty in this example; written to `SetUpPuzzleCategory` (slide8)
  and `PuzzleCategory1` (slide12) as a single run, XML-escaped.

**Anchor flavor chosen**: **named-shape anchors** (Decision 4 flavor 2) — the slot
shapes are uniquely and stably named (`SetUpPuzzle{i}`, `SetUpPuzzleCategory`,
`PuzzleSolution{slot}-{i}`, `PuzzleCategory{slot}`), so no template token-prep is
needed and the real template is the tool's template, unmodified. `SLOT_MAPPING`
records, per game slot, the slide part + the 52 tile shape names + the category
shape name for both the slide8 setup surface and the slide12 board cells.

## Decision 5 — Seeded determinism

- **Decision**: `gamegen` uses a `random.Random` instance. With no seed it is seeded
  from system entropy (unpredictable per run, FR-012); with a supplied integer seed
  it is constructed `random.Random(seed)`, making the per-type sampling deterministic
  given the same season contents. The CLI exposes `--seed`.
- **Rationale**: Satisfies FR-012/SC-006 and makes the random behavior exactly
  testable (a fixed seed pins which puzzles land in which slots). A local `Random`
  instance avoids perturbing global RNG state.
- **Alternatives considered**: seeding the global `random` (rejected — global side
  effect); always-seeded-from-season (rejected by clarification — removes per-run
  variety).

## Decision 6 — Spoiler-free operator output

- **Decision**: The `game` CLI prints only the created file path and the slot counts
  (e.g. "4 Round, 3 Toss-Up, 1 Bonus Round into games/wof001.pptm"); it prints no
  solution and no category. Error messages name counts and seasons, never puzzle
  content (e.g. "season 41 has only 2 Toss-Up puzzles; need 3"). Any test that needs
  to assert injected text reads it back from the package behind the test boundary.
- **Rationale**: FR-009/SC-005 and Constitution II. Mirrors the existing ingest CLI's
  spoiler-free summary and the `--print-puzzles` test-only boundary. *(Resolves
  spoilers-and-errors checklist CHK001–CHK006.)*

## Decision 7 — Category disclosure & error-message hygiene

- **Decision**: Treat the **category** as spoiler-adjacent: it is written into the
  game file but never printed by the tool, same as the solution. Error messages
  describe shortfalls by type and count only.
- **Rationale**: The spoilers checklist (CHK003/CHK004) flagged that a category can
  hint the answer and that error text could leak content. Excluding both from all
  operator output closes those gaps.

## Summary of resolved unknowns / checklist gaps

| Item | Resolved by |
|------|-------------|
| python-pptx vs raw ZIP; macro preservation | Decision 1 |
| puzzle source query (season + type) | Decision 2 |
| smallest-unused-number, gap reuse, rollover | Decision 3 |
| slot → slide → shape mapping (the unknown) | Decision 4 (sentinel-diff spike) |
| seeded reproducibility | Decision 5 |
| no-spoilers operator output (CHK001–006) | Decision 6 |
| category disclosure / error leak (CHK003/004) | Decision 7 |

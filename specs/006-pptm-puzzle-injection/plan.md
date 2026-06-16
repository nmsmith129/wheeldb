# Implementation Plan: PowerPoint Puzzle Injection

**Branch**: `006-pptm-puzzle-injection` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-pptm-puzzle-injection/spec.md`

## Summary

Add a tool that produces a ready-to-play Wheel of Fortune game from the
`WheelofFortune6.4.pptm` template. It selects eight puzzles from a host-named
**season** in the project's ingested store — four Round, three Toss-Up, one Bonus
Round, chosen at random per type (optionally seeded for reproducibility) — and
writes them into the template's eight puzzle slots, saving the result as
`games/wof[N].pptm` (smallest unused three-digit number, never overwriting). The
template's macro project (`ppt/vbaProject.bin`) and every other package part are
preserved **byte-for-byte**: only the specific slide XML parts that carry the eight
slots' solution/category text are rewritten. The generation step is spoiler-free —
it reports the created file and slot counts, never a solution. Correctness is pinned
by an offline test suite over a fixture `.pptm` (asserting the right text lands in
the right slide part and that all other parts, including the VBA, are unchanged).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Python standard library only — `zipfile` + `xml`/`re` for
OOXML part editing, `random` for selection, `argparse` for the CLI. Reuses the
existing `wheeldb` store and `models.Puzzle`. **No `python-pptx`** (it is not
installed and does not round-trip macro-enabled packages safely — see research
Decision 1).

**Storage**: Reads puzzles from the existing ingested SQLite store (feature 002).
Writes a new `.pptm` package under `games/`. (Reading the CSV store from feature 005
is deferred until that feature merges — out of scope here.)

**Testing**: `pytest`, fully offline. A small fixture `.pptm` (or the real template
treated read-only) drives unit tests for slot injection and package preservation,
plus integration tests for season selection, numbering, and the spoiler-free CLI.
No test opens PowerPoint or touches the network (Constitution I & III).

**Target Platform**: Cross-platform Python; the generated file is opened by the
host in PowerPoint (macro-enabled). The tool itself never executes the macros.

**Project Type**: Single project — library + CLI (extends the existing one).

**Performance Goals**: Not latency-critical; one package rewrite per game (a few MB
ZIP), trivial.

**Constraints**: MUST NOT modify the template or its VBA; the generated package
MUST keep `vbaProject.bin` and all non-edited parts byte-identical so macros still
run (FR-004/SC-004). Spoiler-free operator output (FR-009/SC-005, Constitution II).
Offline-testable (Constitution I).

**Scale/Scope**: One game (8 slots) per run; a season holds a few hundred puzzles —
random selection over an in-memory list is trivial.

**NEEDS CLARIFICATION (resolved in Phase 0 research)**:
- How each of the eight slots is located in the template — resolved as **stable
  anchors** (content placeholder tokens, preferred; or unique shape names), never
  positional indices, so injection survives user template edits and PowerPoint
  re-saves (research Decision 4). The token flavor preps the template once with
  benign placeholder text and touches no VBA (FR-004 holds).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against wheeldb Constitution v1.1.1 (6 principles):

| Principle | Gate | Status |
|-----------|------|--------|
| I. Library-First | Game generation is a standalone module (`gamegen`) usable without the CLI and offline; package editing is an independently testable seam (`pptx_inject`). Each has module/function docstrings. | PASS — self-contained, single purpose. |
| II. CLI, No Spoilers | The CLI reports the created file and slot counts to stdout, errors to stderr, and never prints a solution or category. The generated `.pptm` necessarily contains solutions (it is the product), but no operator output reveals them. | PASS — see contracts/cli.md; FR-009. |
| III. Test-First (NON-NEGOTIABLE) | Every behavioral unit (slot injection, package-preservation, numbering, season selection, seeded determinism, CLI) gets a failing test before implementation; an integration test exercises end-to-end generation over a fixture package. Enforced by the `PreToolUse(Write)` guard. | PASS — tasks will order tests first. |
| IV. Reuse Before Creation | Reuses the `wheeldb` store and `models.Puzzle`; adds one read query (`puzzles_for_season`) to `storage.py` rather than a parallel data path. Selection reuses the existing puzzle-type derivation. | PASS — one new query + two new modules, no duplication. |
| V. Debuggable Tests | Tests print the chosen season, the per-type selection, the target slide parts, and a diff summary of which package parts changed, so a failure is diagnosable from the log. | PASS — asserted in test design. |
| VI. Documented Methods | Every new method (selection, numbering, slot injection, package read/write, CLI) is preceded by a docstring stating purpose, parameters, and return/raises. | PASS — enforced in tasks/review. |

**Spoiler note (Principle II)**: tests that need to assert puzzle text landed in a
slide part must do so behind the test boundary (like the existing
`print_helpers`/`--print-puzzles` pattern), never via normal CLI output.

**Additional Constraints**: offline-capable tests — satisfied via a fixture package;
respectful scraping — N/A (no network). **No violations; Complexity Tracking not
required.**

## Project Structure

### Documentation (this feature)

```text
specs/006-pptm-puzzle-injection/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 — macro-safe editing, slot mapping spike
├── data-model.md        # Phase 1 — entities: game request, slot map, selection
├── quickstart.md        # Phase 1 — offline validation scenarios
├── contracts/
│   ├── cli.md           # `wheeldb game <season> [--seed] [--db] [--games-dir]` contract
│   ├── injector-contract.md   # package read/edit/write + slot-injection contract
│   └── library-api.md   # new public surface (gamegen, puzzles_for_season)
├── checklists/
│   ├── requirements.md          # spec quality (from /speckit-specify)
│   └── spoilers-and-errors.md   # behavior checklist (from /speckit-checklist)
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
└── wheeldb/
    ├── storage.py          # + puzzles_for_season(season) read query (REUSED store)
    ├── models.py            # (unchanged) Puzzle + type/number derivations — REUSED
    ├── errors.py            # + GameError(WheelDBError) for generation failures
    ├── pptx_inject.py       # NEW: macro-safe OOXML package read / slot-write / save
    ├── gamegen.py           # NEW: season selection + slot assignment + numbering
    └── cli.py               # + `game` subcommand (season, --seed, --db, --games-dir)

games/                       # NEW output dir (created on first run); gitignored
tests/
├── fixtures/
│   └── wof_template.pptm    # small fixture package with the 8 slots (or real template, read-only)
├── unit/
│   ├── test_pptx_inject.py  # NEW: slot text written; vbaProject.bin + other parts byte-identical
│   ├── test_gamegen.py      # NEW: per-type random selection, seeded determinism, numbering, errors
│   └── test_storage.py      # + puzzles_for_season query
└── integration/
    └── test_game.py         # NEW: end-to-end CLI -> games/wof001.pptm, spoiler-free, numbering
```

**Structure Decision**: Single-project library layout (matches 001/002/005). Two new
single-purpose modules: `pptx_inject.py` owns all OOXML/ZIP concerns (the only place
that knows the package layout and how to preserve it), and `gamegen.py` owns
selection + slot assignment + file numbering, gluing the store to the injector. The
CLI gains one thin `game` subcommand. A small read query is added to the existing
store rather than duplicating data access (Principle IV).

## Complexity Tracking

> No Constitution Check violations. No entries required.

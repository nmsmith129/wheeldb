# Implementation Plan: Episode Puzzle Parser

**Branch**: `main` | **Date**: 2026-06-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-episode-puzzle-parser/spec.md`

## Summary

Given a Wheel of Fortune episode number, the feature returns every puzzle that
aired in that episode as a list of `Puzzle` objects, each exposing solution,
category, date, season number, episode number, and round. Data is sourced from
the Buy A Vowel Boards compendium, which organizes puzzles into one table per
season page (no per-episode page). The system therefore searches season pages,
matches the `EP#` column, and normalizes each matched row per FORMAT.md. The
design is a small Python library (parser + fetch + models + lookup) with a thin,
spoiler-free CLI; correctness is pinned by an offline test suite over saved HTML
fixtures, with a test-only option to print parsed puzzles.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `requests` (HTTP with a real browser User-Agent +
politeness delay), `beautifulsoup4` (HTML table parsing, table selection by
header signature). Standard library `datetime` for date normalization.

**Storage**: N/A for this feature — the parser returns objects; the project's
SQLite persistence layer is out of scope here (spec Assumptions).

**Testing**: `pytest`. Offline suite over saved season-page HTML fixtures; the
HTTP layer is mocked so no test touches the live site (Constitution I & III).

**Target Platform**: Cross-platform (Windows/macOS/Linux), Python runtime.

**Project Type**: Single project — library + CLI.

**Performance Goals**: Not latency-critical. Live fetches honor a politeness
delay; episode lookup short-circuits as soon as the containing season is found
rather than fetching all 43 season pages.

**Constraints**: Offline-capable test suite (fixtures + mocked HTTP); real
browser `User-Agent` required (site returns HTTP 403 otherwise); requests are
serialized with a politeness delay; no puzzle solutions printed outside tests
(Constitution II).

**Scale/Scope**: 43 seasons (1983→present), episode numbers up to ~8000+, ~3–6
puzzle rows per episode.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against wheeldb Constitution v1.1.1 (6 principles):

| Principle | Gate | Status |
|-----------|------|--------|
| I. Library-First | Feature is a standalone `wheeldb` library module usable without the CLI and without live network (fixtures + mocked HTTP); each module (models, parser, fetch, lookup) independently testable; module/function docstrings. | PASS — design splits into self-contained modules; no organizational-only modules. |
| II. CLI, No Spoilers | CLI takes the episode number as an arg, writes counts/provenance to stdout and errors to stderr, and never prints solutions. Solutions surface only behind the test boundary. | PASS — FR-012/FR-013; CLI contract emits counts + provenance only. |
| III. Test-First (NON-NEGOTIABLE) | Tests written before implementation; red-green-refactor; integration test across modules before "done". | PASS — tasks will order fixtures + failing tests before implementation. |
| IV. Reuse Before Creation | Single source of truth for normalization (quote/symbol stripping, date, round) reused by row parsing and lookup; no duplicated parsing logic. | PASS — normalization centralized in the parser module. |
| V. Debuggable Tests | Tests print inputs/expected/actual at failure; the test-only print option surfaces parsed puzzles. | PASS — FR-012 print option doubles as debug output. |
| VI. Documented Methods | Every method preceded by a docstring covering purpose + each parameter (+ return). | PASS — enforced in tasks and review. |

Additional Constraints: idempotent runs (N/A — no persistence this feature),
respectful scraping (politeness delay + browser UA — honored in `fetch`),
fixture-backed parsing (the test suite's foundation). **No violations; Complexity
Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/001-episode-puzzle-parser/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── library-api.md   # Public Python surface (extract_episode, Puzzle)
│   ├── cli.md           # CLI command/IO contract (spoiler-free)
│   └── parser-contract.md # Row/table → Puzzle normalization contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
src/
└── wheeldb/
    ├── __init__.py          # Package exports (extract_episode, Puzzle)
    ├── models.py            # Puzzle dataclass + readable-name/type derivations
    ├── normalize.py         # Single source of truth for value normalization
    ├── parser.py            # Locate puzzle table, parse rows → Puzzle list
    ├── fetch.py             # HTTP retrieval: browser UA, politeness, 403 handling
    ├── episodes.py          # extract_episode: season-search + EP# match orchestration
    └── cli.py               # Spoiler-free CLI entry point

tests/
├── conftest.py              # Fixture loaders, mocked fetch, --print-puzzles option
├── fixtures/                # Saved season-page HTML (early/middle/recent eras)
│   ├── compendium1.html
│   ├── compendium20.html
│   └── compendium42.html
├── unit/
│   ├── test_normalize.py    # Quote/symbol stripping, date, round code
│   ├── test_models.py       # Puzzle attributes + derivations
│   └── test_parser.py       # Table selection + row parsing over fixtures
└── integration/
    └── test_extract_episode.py  # Episode number → puzzles, across eras + edge cases
```

**Structure Decision**: Single-project library layout under `src/wheeldb/` with a
parallel `tests/` tree. The library is the deliverable (Principle I); `cli.py` is
a thin spoiler-free wrapper (Principle II). Modules are split by responsibility
(models / normalize / parse / fetch / lookup) so each is independently testable,
and normalization lives in exactly one module to satisfy Principle IV.

## Complexity Tracking

> No Constitution Check violations. No entries required.

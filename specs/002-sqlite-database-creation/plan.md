# Implementation Plan: SQLite Puzzle Database

**Branch**: `002-sqlite-database-creation` | **Date**: 2026-06-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-sqlite-database-creation/spec.md`

## Summary

Add a persistence layer that ingests Wheel of Fortune puzzles into a local SQLite
database, invoked **only** with a single season (`40`) or an inclusive season
range (`37-40`). The scraper is confined to exactly the requested season(s):
each season's page is fetched via the existing `Fetcher` seam, parsed with the
existing `find_puzzle_table` + `parse_rows` (no new parsing path, FR-001), and
every resulting `Puzzle` is written as one row carrying its six source attributes
plus the derived `puzzle_number` and `puzzle_type`. Rows are keyed on
`(season, episode, round)` and written with an idempotent UPSERT so re-runs
update in place and never duplicate (FR-007). Ingestion is **best-effort per
season**: each season is its own transaction (atomic — all its rows or none,
FR-011a); a season that cannot be retrieved is reported and skipped while the
other seasons still commit (FR-011); a data error (an unrecognized round code
that cannot yield a puzzle number) rolls back its season and halts the run,
retaining seasons committed earlier (FR-010). Persistence uses the Python
standard-library `sqlite3` module — no new
dependency. Correctness is pinned by an offline test suite over a temporary
database file and the existing season-page fixtures.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Standard-library `sqlite3` for storage (no new
third-party dependency); reuses existing `requests`/`beautifulsoup4` only
indirectly through the established `fetch` + `parser` modules.

**Storage**: SQLite, single file (default path in the workspace, overridable).
One table, `puzzles`, with a composite primary key on `(season, episode, round)`.

**Testing**: `pytest`. New unit tests for the season-argument parser and the
storage layer (against a `tmp_path` database), plus integration tests for the
end-to-end ingest over saved season fixtures. No test touches the live site or a
persistent database (Constitution I & III).

**Target Platform**: Cross-platform (Windows/macOS/Linux), Python runtime.

**Project Type**: Single project — library + CLI (extends the existing one).

**Performance Goals**: Not latency-critical. A single season has a few hundred
puzzle rows at most; a range is processed season-by-season honoring the existing
politeness delay on live fetches.

**Constraints**: Idempotent runs (UPSERT on the stable key); spoiler-free CLI
output (counts/provenance only, Constitution II); offline-capable test suite;
per-season atomic writes with best-effort range processing — a season is
committed whole or skipped whole, so a run never leaves an individual season
half-written (FR-011/FR-011a).

**Scale/Scope**: 43 seasons; a season page parses to roughly 150–250 puzzle rows;
a full-history backfill is ~6–9k rows. Well within SQLite's comfort zone.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against wheeldb Constitution v1.1.1 (6 principles):

| Principle | Gate | Status |
|-----------|------|--------|
| I. Library-First | Persistence is a standalone `storage` module (a `PuzzleStore` over `sqlite3`) usable without the CLI and without network; ingest orchestration is a separate `ingest` module. Both are independently testable offline (temp DB + fixture fetcher). Each has module/function docstrings. | PASS — two self-contained, single-purpose modules; no organizational-only grouping. |
| II. CLI, No Spoilers | New `ingest` subcommand takes a season/range arg, writes a counts+provenance summary to stdout and diagnostics/errors to stderr, and never prints a solution. The database file holds solutions (it is the product), but no solution is printed. | PASS — see contracts/cli.md; FR-009. |
| III. Test-First (NON-NEGOTIABLE) | Every behavioral unit (arg parsing, schema creation, upsert/idempotency, row mapping incl. derived columns, abort/transaction, CLI) gets a failing test before implementation; an integration test exercises ingest end-to-end before "done". Enforced by the `PreToolUse(Write)` guard. | PASS — tasks will order tests first. |
| IV. Reuse Before Creation | Ingestion reuses `fetch.Fetcher`, `parser.find_puzzle_table`/`parse_rows`, `models.Puzzle` and its `puzzle_number`/`puzzle_type` derivations, and the `errors.WheelDBError` hierarchy (adding one `DatabaseError` subclass). No parsing, normalization, or HTTP logic is duplicated. | PASS — new code is storage + orchestration only. |
| V. Debuggable Tests | Storage/ingest tests print the season(s) processed, the rows written, expected vs actual counts, and the offending round code on an abort path, so a failure is diagnosable from the log alone. | PASS — asserted in test design. |
| VI. Documented Methods | Every new method (store open/upsert/count, ingest orchestration, season-arg parser) is preceded by a docstring stating purpose, each parameter, and return/raises. | PASS — enforced in tasks and review. |

**Additional Constraints**: idempotent runs — satisfied by the `(season, episode,
round)` primary key + UPSERT; respectful scraping — unchanged, inherited from
`fetch`; fixture-backed parsing — unchanged, reused. **No violations; Complexity
Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/002-sqlite-database-creation/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli.md           # `ingest <season|range>` command/IO contract (spoiler-free)
│   ├── storage-contract.md  # PuzzleStore: schema, UPSERT/idempotency, row mapping
│   └── library-api.md   # New public surface: ingest_seasons, parse_season_arg, PuzzleStore
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks - NOT created here)
```

### Source Code (repository root)

```text
src/
└── wheeldb/
    ├── __init__.py          # + export ingest_seasons, PuzzleStore, DatabaseError
    ├── models.py            # (unchanged) Puzzle + puzzle_number/puzzle_type/puzzle_id
    ├── normalize.py         # (unchanged) value normalization
    ├── parser.py            # (unchanged) find_puzzle_table, parse_rows — REUSED
    ├── fetch.py             # (unchanged) Fetcher seam, HttpFetcher — REUSED
    ├── episodes.py          # (unchanged) extract_episode (read-only lookup)
    ├── errors.py            # + DatabaseError(WheelDBError)
    ├── storage.py           # NEW: PuzzleStore — sqlite3 schema + idempotent UPSERT
    ├── ingest.py            # NEW: parse_season_arg + ingest_seasons orchestration
    └── cli.py               # + `ingest` subcommand (season|range, --db)

tests/
├── conftest.py              # (reused) FixtureFetcher; may add a spy/bounded fetcher
├── fixtures/                # (reused) compendium1/20/42.html
├── unit/
│   ├── test_storage.py      # NEW: schema, UPSERT idempotency, row mapping, DatabaseError
│   └── test_ingest_args.py  # NEW: parse_season_arg ("40", "37-40", "40-40", rejects)
└── integration/
    └── test_ingest.py       # NEW: end-to-end ingest, idempotent re-run, range,
                             #      bounded fetch, abort-leaves-db-unchanged, CLI summary
```

**Structure Decision**: Single-project library layout (matches feature 001). Two
new single-purpose modules: `storage.py` owns all SQLite concerns (the only place
that knows the schema and SQL), and `ingest.py` owns the season-argument contract
plus the season-loop orchestration that glues `fetch` → `parser` → `storage`. The
CLI gains one thin `ingest` subcommand. This keeps the storage seam independently
testable (Principle I) and the SQL in exactly one module (Principle IV).

## Complexity Tracking

> No Constitution Check violations. No entries required.

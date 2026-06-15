# Implementation Plan: CSV Output Format

**Branch**: `005-csv-output-format` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-csv-output-format/spec.md`

## Summary

Add a CSV output format as a drop-in alternative to the SQLite store. A new
`CsvPuzzleStore` mirrors `PuzzleStore`'s interface (context manager,
`transaction()`, `upsert()` returning `"added"`/`"updated"`, `count()`,
`count_for_season()`) so the existing `ingest_seasons` orchestration drives it
unchanged through duck typing — no second ingest path. The ingest CLI gains a
`--format {sqlite,csv}` option (default `sqlite`, preserving today's behavior);
when `csv` is selected the output path is the existing `--db` path with its
extension swapped to `.csv` (FR-002a). A CSV row serializes the puzzle as
`season, episode, date, puzzle_type, puzzle_number, category, solution, flags`
(FR-003); `flags` reuses the same JSON encoding the SQLite store uses. The store
de-duplicates and edits in place keyed on the stable identity
`(season, episode, round)`; because `round` is not a column, it is reconstructed
from `puzzle_type` + `puzzle_number` via a single inverse-mapping helper added to
`models.py` (the module that owns the forward derivation), keeping one source of
truth (Principle IV). The store reads-merges-rewrites the whole file per
transaction with an atomic temp-file replace, giving the same idempotency,
added/updated counts, best-effort-per-season, and all-or-nothing-per-season
guarantees as SQLite. A pre-existing file whose header does not exactly match the
expected columns halts the run via `DatabaseError`, leaving the file untouched
(FR-012). No solutions are printed (Principle II). Correctness is pinned by an
offline test suite over `tmp_path` files and the existing season fixtures.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Standard-library `csv` and `json` for the CSV store (no
new third-party dependency); reuses the established `fetch` + `parser` + `models`
+ `ingest` modules and the `errors.WheelDBError` hierarchy.

**Storage**: A single plain-text CSV file as the alternative persistence target to
the SQLite database. One header row plus one data row per puzzle; the de-dup
identity is `(season, episode, round)`, with `round` reconstructed from the
`puzzle_type`/`puzzle_number` columns on read.

**Testing**: `pytest`. New unit tests for `CsvPuzzleStore` (against `tmp_path`
files — round-trip, idempotency, header-mismatch, atomic rollback), the
round-reconstruction helper in `models`, and the path-derivation helper; reuse the
existing fixture-backed integration tests for `ingest` extended with the CSV
format. No test touches the live site or a persistent file (Constitution I & III).

**Target Platform**: Cross-platform (Windows/macOS/Linux), Python runtime. CSV is
written with `newline=""` and explicit `\n` line terminator so quoting and line
endings round-trip identically across platforms.

**Project Type**: Single project — library + CLI (extends the existing one).

**Performance Goals**: Not latency-critical. Read-merge-rewrite of one CSV file per
season transaction; a full-history file is ~6–9k rows, trivially held in memory.

**Constraints**: Observable-behavior parity with the SQLite path (idempotency,
added/updated/total/skipped/unparsed counts, best-effort range, all-or-nothing per
season, no spoilers — Constitution II); offline-capable test suite; default
behavior unchanged when `--format` is omitted (FR-002).

**Scale/Scope**: 43 seasons; ~150–250 rows per season page; a full backfill is
~6–9k rows — comfortably an in-memory dict keyed on `(season, episode, round)`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against wheeldb Constitution v1.1.1 (6 principles):

| Principle | Gate | Status |
|-----------|------|--------|
| I. Library-First | `CsvPuzzleStore` is a standalone single-purpose module (`csv_storage.py`) usable without the CLI and without network, independently testable offline against a `tmp_path` file. The round inverse-mapping is a pure function in `models`. | PASS — self-contained, single purpose. |
| II. CLI, No Spoilers | The `--format` option only selects a persistence target; the summary still reports counts/provenance to stdout and errors to stderr, never a solution. The CSV file holds solutions (it is the product), but no path prints one. | PASS — see contracts/cli.md; FR-010. |
| III. Test-First (NON-NEGOTIABLE) | Every behavioral unit (round reconstruction, path derivation, CSV open/header-validate, upsert/idempotency, transaction rollback, count, CLI `--format` wiring) gets a failing test before implementation; integration tests exercise CSV ingest end-to-end before "done". Enforced by the `PreToolUse(Write)` guard. | PASS — tasks will order tests first. |
| IV. Reuse Before Creation | Reuses `ingest_seasons` (unchanged loop), `models.Puzzle` + its `puzzle_number`/`puzzle_type` derivations (and a new co-located inverse helper), the JSON flags encoding from `storage`, and `errors.DatabaseError`/`PuzzleParseError`. `CsvPuzzleStore` deliberately mirrors `PuzzleStore`'s method names so the orchestration is shared, not duplicated. | PASS — no parsing/orchestration duplication. |
| V. Debuggable Tests | Store/ingest tests print the file path, the expected vs actual header, the rows written, the reconstructed keys, and added/updated counts at the point of failure. | PASS — asserted in test design. |
| VI. Documented Methods | Every new method (store open/upsert/count/transaction/commit/rollback, the inverse-mapping helper, the path-derivation helper) is preceded by a docstring stating purpose, each parameter, and return/raises. | PASS — enforced in tasks and review. |

**Additional Constraints**: idempotent runs — satisfied by the `(season, episode,
round)` in-memory key + last-wins overwrite; respectful scraping — unchanged,
inherited from `fetch`; fixture-backed parsing — unchanged, reused. **No
violations; Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/005-csv-output-format/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — resolved CSV-format decisions
├── data-model.md        # Phase 1 output — CSV row schema + identity
├── quickstart.md        # Phase 1 output — runnable validation scenarios
├── contracts/           # Phase 1 output
│   ├── cli.md           # `ingest --format {sqlite,csv}` command/IO contract
│   ├── csv-store-contract.md  # CsvPuzzleStore: columns, header rule, upsert, atomicity
│   └── library-api.md   # New public surface: CsvPuzzleStore, round_from_type_and_number
├── checklists/
│   ├── requirements.md  # Spec quality checklist (from /speckit-specify)
│   └── csv.md           # CSV behavior requirements checklist (from /speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks - NOT created here)
```

### Source Code (repository root)

```text
src/
└── wheeldb/
    ├── __init__.py          # + export CsvPuzzleStore
    ├── models.py            # + round_from_type_and_number() inverse helper (co-located)
    ├── parser.py            # (unchanged) — REUSED via ingest
    ├── fetch.py             # (unchanged) — REUSED via ingest
    ├── errors.py            # (unchanged) — reuse DatabaseError / PuzzleParseError
    ├── storage.py           # (unchanged) PuzzleStore — the parity reference
    ├── csv_storage.py       # NEW: CsvPuzzleStore — read-merge-rewrite CSV, header-validated
    ├── ingest.py            # CHANGED: select store by format (store factory / fmt param)
    └── cli.py               # + `--format {sqlite,csv}` and `.csv` path derivation

tests/
├── conftest.py              # (reused) FixtureFetcher
├── fixtures/                # (reused) compendium1/20/42.html
├── unit/
│   ├── test_models.py       # + round_from_type_and_number cases (incl. reject)
│   ├── test_csv_storage.py  # NEW: header validate, round-trip, idempotency, rollback, count
│   └── test_csv_path.py     # NEW: path-derivation (.sqlite→.csv, no-ext→append)
└── integration/
    └── test_ingest.py       # + CSV-format end-to-end, idempotent re-run, range, parity
```

**Structure Decision**: Single-project library layout (matches features 001/002).
The CSV concern lives in one new module, `csv_storage.py`, exactly mirroring the
seam `storage.py` established — so `ingest_seasons` drives either store without a
second code path. The only edit to existing behavior is (a) `ingest` selecting the
store by format and (b) `cli` adding the `--format` option and deriving the `.csv`
path. The round inverse-mapping is added next to its forward counterpart in
`models.py` to keep a single source of truth (Principle IV).

## Complexity Tracking

> No Constitution Check violations. No entries required.

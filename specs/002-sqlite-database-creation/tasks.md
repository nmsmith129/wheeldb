---

description: "Task list for SQLite Puzzle Database"
---

# Tasks: SQLite Puzzle Database

**Input**: Design documents from `/specs/002-sqlite-database-creation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: REQUIRED. Constitution Principle III (Test-First) is NON-NEGOTIABLE and
is enforced by the `PreToolUse(Write)` guard (`.claude/hooks/test_first_guard.py`),
which blocks writing a `src/wheeldb/` module unless a test referencing it is
currently FAILING. Every implementation task below is therefore preceded by a
failing-test task. Run `py -m pytest` and observe RED before writing source.

**Organization**: Tasks are grouped by user story (from spec.md) for independent
implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, and Polish carry no story label)
- File paths are exact and repo-relative.

## Path Conventions

Single project: `src/wheeldb/` and `tests/` at repository root (matches feature 001).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test scaffolding the stories rely on. No production code; not gated by the test-first hook (these are test-support files).

- [X] T001 [P] Add a `RecordingFetcher` to `tests/conftest.py`: an offline `Fetcher` that serves multiple `compendium{N}.html` fixtures and records the season numbers it was asked for (exposes e.g. `requested` list), for bounded-fetch and range tests. Mirror the existing `FixtureFetcher` docstring/style.
- [X] T002 [P] Add a minimal synthetic fixture `tests/fixtures/compendium_badround.html` containing the puzzle-table header signature plus one data row whose ROUND cell is an unrecognized code (e.g. `XX`), for the data-error abort test. Document its purpose in a comment.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The persistence container and the shared input parser that every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Write FAILING unit tests in `tests/unit/test_storage.py` for `PuzzleStore` open/schema: opening a `tmp_path` file creates the DB and a `puzzles` table matching `data-model.md` (assert columns + composite PK via `PRAGMA table_info`/`PRAGMA index_list`); re-opening is idempotent; an unopenable path raises `wheeldb.errors.DatabaseError`. Print expected vs actual schema on failure (Principle V).
- [X] T004 [P] Write FAILING unit tests in `tests/unit/test_ingest_args.py` for `parse_season_arg`: `"40"`→`[40]`, `"37-40"`→`[37,38,39,40]`, `"40-40"`→`[40]`; and `ValueError` for `"40-37"`, `""`, `"abc"`, `"-5"`, `"3-"`, `"a-b"`. Print the input and result/exception on failure.
- [X] T005 Add `class DatabaseError(WheelDBError)` with a docstring to `src/wheeldb/errors.py` (extends the existing hierarchy — Principle IV). Makes T003's error path importable.
- [X] T006 Implement `PuzzleStore` in `src/wheeldb/storage.py` to pass T003: constructor opens/creates the DB at a given path, runs `CREATE TABLE IF NOT EXISTS puzzles (...)` per `data-model.md`, supports context-manager use and a `transaction()` context manager plus `begin/commit/rollback`, and provides `count()` / `count_for_season(season)`. Raise `DatabaseError` on sqlite/open failures. Docstring every method (Principle VI).
- [X] T007 Implement `parse_season_arg(text) -> list[int]` in `src/wheeldb/ingest.py` to pass T004 (single value, inclusive ascending range, equal endpoints; reject malformed/reversed with `ValueError`). Full docstring.

**Checkpoint**: A database can be opened/created and a season argument resolved to a season list. No puzzles are written yet.

---

## Phase 3: User Story 1 - Ingest a single season (Priority: P1) 🎯 MVP

**Goal**: Run the ingest action with one season; every parsed puzzle becomes one row carrying all six source attributes plus derived `puzzle_number`/`puzzle_type`. The run is atomic (a data error or retrieval failure leaves the DB unchanged).

**Independent Test**: Ingest a fixture season into a `tmp_path` DB and confirm one row per parsed puzzle with correct attribute and derived values; confirm an aborted run writes zero rows; confirm the CLI prints counts/provenance and no solution.

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [X] T008 [P] [US1] Write FAILING unit tests in `tests/unit/test_storage.py` for `PuzzleStore.upsert`: a `Puzzle` maps to exactly one row with all six attributes plus derived `puzzle_number`/`puzzle_type` and `flags` as a JSON array (`()`→`"[]"`); upserting a `Puzzle` whose round code yields no number raises `PuzzleParseError` and writes no row (assert `count()` unchanged). Print the row read back vs the source puzzle.
- [X] T009 [US1] Write FAILING integration tests in `tests/integration/test_ingest.py` for `ingest_seasons` (single season, `FixtureFetcher`, `tmp_path` DB): stores one row per parsed puzzle with correct values; returns an `IngestSummary` with `total` == rows and empty `skipped`. Data error (the `compendium_badround` fixture) **raises** `PuzzleParseError` and leaves the DB row count unchanged (season rolled back). A single-season `RetrievalError` (unknown season) does **not** raise — it returns a summary with `seasons == []`, `skipped == [that season]`, `total == 0`, and leaves the DB unchanged. Print seasons committed/skipped and counts.
- [X] T010 [US1] Write FAILING integration tests in `tests/integration/test_ingest.py` for the CLI `ingest <season> --db <tmp>`: stdout reports added/updated/total, the season, and the source URL, and contains NO solution text (scan output against known fixture solutions); a malformed argument exits non-zero with a usage message and writes nothing. Drive `cli.main([...], fetcher=FixtureFetcher())`.

### Implementation for User Story 1

- [X] T011 [US1] Add the `IngestSummary` dataclass (`seasons`, `skipped`, `added`, `updated`, `total`) to `src/wheeldb/ingest.py` and implement `PuzzleStore.upsert(puzzle)` in `src/wheeldb/storage.py` as an `INSERT` that maps the puzzle to a row (computing `puzzle_number`/`puzzle_type`, JSON-encoding `flags`); let `PuzzleParseError` from `Puzzle.puzzle_number` propagate without writing. (Conflict/idempotency handling is added in US2.) Pass T008.
- [X] T012 [US1] Implement `ingest_seasons(season_arg, *, db_path, fetcher=None)` in `src/wheeldb/ingest.py`: resolve seasons via `parse_season_arg` (or accept an int iterable), default to `HttpFetcher`, then loop the resolved seasons in ascending order, each in its **own** `PuzzleStore.transaction()`, calling `fetch.get_season_html` → `parser.find_puzzle_table` → `parser.parse_rows` → `store.upsert` (reuse only; no new parsing — FR-001). Best-effort per season (Decision 5): commit a clean season (accruing to `seasons`/`added`/`updated`); on `RetrievalError` roll back that season, append it to `skipped`, and **continue**; on `PuzzleParseError`/`DatabaseError` roll back that season and **re-raise** (halt). Return `IngestSummary` (including when some seasons were skipped). Pass T009. (The loop already accepts multiple seasons; US3 verifies the range + skip cases.)
- [X] T013 [US1] Add the `ingest` subcommand to `src/wheeldb/cli.py`: positional `<season|range>` and optional `--db PATH` (default `wheeldb.sqlite`); call `ingest_seasons`; render the spoiler-free summary to stdout (counts, committed season(s), source URL via `season_url`) and route diagnostics/usage/errors to stderr. Exit non-zero on a bad argument, when the summary reports any `skipped` season, or on a halting data/DB error (per `contracts/cli.md`). Pass T010.
- [X] T014 [US1] Export `ingest_seasons`, `parse_season_arg`, `PuzzleStore`, `IngestSummary`, and `DatabaseError` from `src/wheeldb/__init__.py` (`__all__`), per `contracts/library-api.md`.

**Checkpoint**: Single-season ingest works end-to-end into a fresh database; aborts are atomic; CLI is spoiler-free. MVP deliverable.

---

## Phase 4: User Story 2 - Idempotent re-ingestion (Priority: P2)

**Goal**: Re-ingesting an already-stored season updates rows in place and never duplicates; the summary distinguishes added from updated.

**Independent Test**: Ingest the same fixture season twice; the row count after the second run equals the first, and the second summary reports `updated > 0`, `added == 0`.

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [X] T015 [P] [US2] Write FAILING unit tests in `tests/unit/test_storage.py` for idempotent `upsert`: upserting the same key twice yields one row and returns `"added"` then `"updated"`; a changed attribute (e.g. `solution`/`category`) on the second upsert is reflected in the stored row; `count()` is unchanged after the second upsert. Print before/after row values.
- [X] T016 [US2] Write FAILING integration tests in `tests/integration/test_ingest.py`: (a) `ingest_seasons` of the same season twice leaves the row count unchanged on the second run, and the second `IngestSummary` has `added == 0` and `updated == total` (SC-003); (b) **additive/no-prune (FR-007a)** — pre-seed the DB with an extra row for the same season that the current parse does NOT produce (e.g. an extra round), re-ingest the season, and assert that pre-existing row is still present afterward (re-ingestion never deletes rows absent from the new parse). Print both summaries and the surviving extra row.

### Implementation for User Story 2

- [X] T017 [US2] Upgrade `PuzzleStore.upsert` in `src/wheeldb/storage.py` to `INSERT ... ON CONFLICT(season, episode, round) DO UPDATE SET ...`, returning `"added"`/`"updated"` via a `SELECT 1` existence check in the same transaction; add `upsert_many(puzzles) -> (added, updated)`; and have `ingest_seasons` populate `IngestSummary.added`/`updated` from the tallies. Pass T015 and T016.

**Checkpoint**: Re-runs are idempotent and report added vs updated. User Stories 1 AND 2 both pass.

---

## Phase 5: User Story 3 - Ingest a season range (Priority: P3)

**Goal**: Supplying a range (`37-40`) ingests every season in the inclusive range; only those seasons are fetched; the summary lists every source.

**Independent Test**: Ingest a multi-season fixture range and confirm one row per puzzle for each season in range and none outside it, proven by the `RecordingFetcher` having requested exactly the in-range seasons.

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [X] T018 [US3] Write FAILING integration tests in `tests/integration/test_ingest.py` using `RecordingFetcher` over several fixture seasons: (a) ingesting a range stores rows for every season in the inclusive range and none outside it, and `fetcher.requested` equals exactly the in-range season list (FR-008a / SC-008); (b) **best-effort skip (FR-011 / SC-009)** — with one in-range season's fixture absent (fetcher raises `RetrievalError` for it), the other seasons are still committed, the returned `IngestSummary.skipped` equals `[that season]`, `seasons` excludes it, and the DB holds rows only for the committed seasons. Print committed vs skipped seasons.
- [X] T019 [US3] Write FAILING integration test in `tests/integration/test_ingest.py` for the CLI with a range argument: stdout lists each committed season's source URL under a `Sources:` block and contains no solution; when a season is skipped, stdout names the skipped season and the process exits non-zero (per `contracts/cli.md`).

### Implementation for User Story 3

- [X] T020 [US3] Extend the CLI summary rendering in `src/wheeldb/cli.py` to print the multi-line `Sources:` block (one `season_url` per committed season), season-range wording when more than one season is committed, and a `Skipped:` line naming any `IngestSummary.skipped` seasons (exiting non-zero when present). Pass T018/T019. (Core range looping already exists from T012; this story verifies bounded fetch + best-effort skip and finalizes range output.)

**Checkpoint**: Single-season and range ingestion both work; the scraper is provably confined to the requested seasons. All user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and whole-suite validation.

- [X] T021 [P] Update `README.md` with the `wheeldb ingest <season|range> [--db PATH]` usage, the default DB path, and a note that the database holds solutions while the CLI stays spoiler-free.
- [X] T022 [P] Docstring/lint pass over `src/wheeldb/storage.py` and `src/wheeldb/ingest.py` (Principle VI); run `py -m ruff check src tests` and resolve findings.
- [X] T023 Run the full offline suite `py -m pytest -ra` and confirm green (including the existing 001 tests — integration across features, Principle III).
- [X] T024 Execute the [quickstart.md](quickstart.md) validation scenarios (offline manual check + idempotency re-run) and confirm the Definition of Done items.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: depends on Foundational. MVP.
- **User Story 2 (Phase 4)**: depends on Foundational; builds on US1's `upsert` (upgrades it). Test T015/T016 first.
- **User Story 3 (Phase 5)**: depends on Foundational; relies on US1's `ingest_seasons` loop. Independently testable.
- **Polish (Phase 6)**: depends on all desired stories.

### Test-first ordering (within every story)

- The test task(s) MUST be written and observed FAILING before the implementation task in the same story (Principle III; enforced by the Write hook).
- Foundational: T003/T004 (tests) before T005–T007 (impl).
- US1: T008–T010 (tests) before T011–T014 (impl).
- US2: T015–T016 (tests) before T017 (impl).
- US3: T018–T019 (tests) before T020 (impl).

### Story independence

- US1 is a complete MVP on a fresh database.
- US2 adds idempotency without breaking US1 (same `upsert` method, conflict clause added).
- US3 adds range verification + multi-source output without breaking US1/US2.

---

## Parallel Opportunities

- **Setup**: T001 and T002 are different files → run in parallel.
- **Foundational tests**: T003 (`test_storage.py`) and T004 (`test_ingest_args.py`) are different files → parallel. T005 and T006/T007 touch different source files but T006 depends on T005 only for the error import; T007 is independent of T005/T006.
- **US1 tests**: T008 (`test_storage.py`) is `[P]` vs T009/T010 (`test_ingest.py`, same file → sequential with each other).
- **US2 tests**: T015 (`test_storage.py`) is `[P]` vs T016 (`test_ingest.py`).
- **Polish**: T021 and T022 are different files → parallel.

> Tasks editing the same file (e.g. T009/T010, T011/T017 in `storage.py`) are NOT parallel.

### Parallel example — Foundational

```bash
# Author the two foundational failing-test files together:
Task: "Write failing PuzzleStore open/schema tests in tests/unit/test_storage.py"   # T003
Task: "Write failing parse_season_arg tests in tests/unit/test_ingest_args.py"        # T004
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (store container + arg parser).
2. Phase 3 US1: single-season ingest, atomic aborts, spoiler-free CLI.
3. **STOP and VALIDATE**: ingest a fixture season into a temp DB; confirm rows + derived columns; confirm an aborted run writes nothing.
4. Demo: `wheeldb ingest 40`.

### Incremental delivery

1. Setup + Foundational → container ready.
2. US1 → single-season ingest (MVP) → validate → demo.
3. US2 → idempotent re-ingestion → validate (re-run, no duplicates) → demo.
4. US3 → season-range + bounded fetch → validate → demo.
5. Polish → docs + full-suite green.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- Every `src/wheeldb/` write is gated: confirm the relevant test is RED first, then implement to GREEN.
- Reuse, don't duplicate: ingestion calls existing `fetch`, `parser`, `models`, `errors` (Principle IV) — the only new production files are `storage.py`, `ingest.py`, plus additions to `errors.py`, `cli.py`, `__init__.py`.
- No new third-party dependency (stdlib `sqlite3` + `json`).
- Commit after each task or logical red→green pair.

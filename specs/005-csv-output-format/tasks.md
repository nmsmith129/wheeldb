---

description: "Task list for CSV Output Format"
---

# Tasks: CSV Output Format

**Input**: Design documents from `/specs/005-csv-output-format/`

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

Single project: `src/wheeldb/` and `tests/` at repository root (matches features 001/002).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test scaffolding the CSV stories rely on. No production code; not gated by the test-first hook (test-support file).

- [ ] T001 [P] Add `tests/csv_helpers.py` with a `read_csv_rows(path)` helper (and a `read_header(path)` helper) that read a CSV back with the stdlib `csv` module for round-trip assertions across the CSV tests. Mirror the style/docstrings of the existing `tests/print_helpers.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The CSV persistence container that every user story builds on (the analogue of feature 002's `PuzzleStore` open/schema container).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 [P] Write FAILING unit tests in `tests/unit/test_csv_storage.py` for the `CsvPuzzleStore` container: opening an absent path yields an empty store (`count()` == 0, `count_for_season()` == 0); committing an empty store writes a **header-only** file equal to the canonical 8-column header `season,episode,date,puzzle_type,puzzle_number,category,solution,flags` (FR-003 + edge "zero puzzles → valid header-only file"); context-manager use works; `transaction()` rolls back to the prior state on an exception; an empty/zero-byte file opens as "no data". Print expected vs actual header/contents on failure (Principle V).
- [ ] T003 Implement the `CsvPuzzleStore` container in `src/wheeldb/csv_storage.py` to pass T002: `__init__(path)` (absent/empty file → empty insertion-ordered dict), the canonical header constant, `__enter__`/`__exit__`, `transaction()` (snapshot dict on entry, `commit()` on clean exit, `rollback()` + re-raise on exception), `commit()` (atomically write header + staged rows to a sibling temp file then `os.replace`), `rollback()` (restore snapshot), `count()`, `count_for_season(season)`. Open files with `newline=""`, `lineterminator="\n"`, UTF-8 (research Decision 1). Docstring every method (Principle VI).

**Checkpoint**: A CSV store can be created and produces a valid header-only file; no puzzle rows yet.

---

## Phase 3: User Story 1 - Ingest puzzles to a CSV file (Priority: P1) 🎯 MVP

**Goal**: Selecting the CSV format writes each parsed puzzle as one row — `season, episode, date, puzzle_type, puzzle_number, category, solution, flags` — to a `.csv` file derived from the `--db` path; the default (no `--format`) is unchanged SQLite.

**Independent Test**: Ingest a fixture season with `--format csv` into a `tmp_path` file; confirm the canonical header plus one row per parsed puzzle with correct values and special characters round-tripping; confirm omitting `--format` still writes SQLite; confirm the CLI prints counts/provenance and no solution.

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [ ] T004 [P] [US1] Write FAILING unit tests in `tests/unit/test_csv_storage.py` for `upsert`/serialization: upserting a `Puzzle` into an empty store returns `"added"`; after `commit()` the file has the canonical header plus one row per puzzle with columns in the contracted order; `flags` serialize as a JSON array (`()` → `"[]"`), `date` is written verbatim, integers as text; a `category`/`solution` containing a comma, a double-quote, **and an embedded newline** round-trips back identically via `read_csv_rows` (FR-003/FR-006/FR-007, SC-004). Print source puzzle vs read-back row.
- [ ] T005 [P] [US1] Write FAILING unit tests in `tests/unit/test_csv_path.py` for the `.csv` path-derivation helper: `wheeldb.sqlite` → `wheeldb.csv`, `wheeldb` → `wheeldb.csv`, `my.data.sqlite` → `my.data.csv` (FR-002a). Print each input → output.
- [ ] T006 [US1] Write FAILING integration tests in `tests/integration/test_ingest.py` for CSV ingest (`FixtureFetcher`, `tmp_path`): ingesting one season with the CSV format creates the `.csv` file with the canonical header and one row per parsed puzzle; the returned `IngestSummary.total` == rows and `skipped` == []. **Count parity (SC-002)**: ingest the same fixture season to SQLite and to CSV and assert the two `IngestSummary` objects report identical `added`, `updated`, `total`, `skipped`, and `unparsed`. Print rows written and both summaries.
- [ ] T007 [US1] Write FAILING integration tests in `tests/integration/test_ingest.py` for the CLI via `cli.main([...], fetcher=FixtureFetcher())`: `ingest 42 --format csv --db <tmp>.sqlite` writes `<tmp>.csv` (not `.sqlite`), stdout reports added/total and names the `.csv` file and contains NO solution text (scan against known fixture solutions); omitting `--format` still writes the SQLite DB unchanged (FR-002); an invalid `--format` value exits non-zero (FR-011).

### Implementation for User Story 1

- [ ] T008 [US1] Implement `CsvPuzzleStore.upsert(puzzle)` in `src/wheeldb/csv_storage.py`: read `puzzle.puzzle_number` first so a `PuzzleParseError` propagates before any mutation (FR-010); key = `(season, episode, puzzle.round)`; serialize the row using the derived `puzzle_type`/`puzzle_number`, `date` verbatim, and `flags` via `json.dumps([list(pair) for pair in puzzle.flags])` (reuse the encoding from `storage.py` — Principle IV); return `"updated"` if the key is already present else `"added"`; store the row (last wins). Pass T004.
- [ ] T009 [US1] Add a private `_csv_output_path(db_path) -> str` helper in `src/wheeldb/cli.py` using `pathlib.Path(db_path).with_suffix(".csv")` per FR-002a (internal to the CLI — not part of the public library surface in [contracts/library-api.md](contracts/library-api.md)). Pass T005.
- [ ] T010 [US1] Add `--format {sqlite,csv}` (argparse `choices`, default `"sqlite"`) to the `ingest` subparser in `src/wheeldb/cli.py`; when `csv`, derive the output path via the T009 `_csv_output_path` helper and pass the format + path to `ingest_seasons`; render the summary naming the actual output file. Argparse rejects an invalid value with a non-zero exit (FR-011). Pass the CLI parts of T007.
- [ ] T011 [US1] Modify `ingest_seasons` in `src/wheeldb/ingest.py` to select the store by format: add a `store_format="sqlite"` parameter and construct `PuzzleStore(path)` (default — unchanged behavior, FR-002) or `CsvPuzzleStore(path)` accordingly. The season loop, `seen_keys` de-duplication, best-effort handling, and `IngestSummary` stay unchanged (the loop is store-agnostic, Principle IV). Pass T006.
- [ ] T012 [US1] Export `CsvPuzzleStore` from `src/wheeldb/__init__.py` (`__all__`) per [contracts/library-api.md](contracts/library-api.md).

**Checkpoint**: Single-season ingest to a fresh CSV works end-to-end; default stays SQLite; CLI is spoiler-free. MVP deliverable.

---

## Phase 4: User Story 2 - Re-ingest is idempotent (Priority: P1)

**Goal**: Re-ingesting into an existing CSV updates matching puzzles in place and never duplicates; the file stays a clean, de-duplicated dataset keyed on `(season, episode, round)` (reconstructed from `puzzle_type`/`puzzle_number`).

**Independent Test**: Ingest a fixture season to CSV twice; the row count after the second run equals the first, the second summary reports `updated == total`, `added == 0`, and a changed source value overwrites the matching row in place.

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [ ] T013 [P] [US2] Write FAILING unit tests in `tests/unit/test_models.py` for `round_from_type_and_number`: `("Bonus Round", 0)` → `"BR"`, `("Toss-Up", 1)` → `"T1"`, `("Round", 2)` → `"R2"`; raises `PuzzleParseError` for an unrecognized pair (e.g. `("Unknown", 3)`). Print each input → output/exception.
- [ ] T014 [US2] Write FAILING unit tests in `tests/unit/test_csv_storage.py` for existing-file behavior: opening a CSV written by a prior run loads its rows (`count()` reflects the file; keys reconstructed via round); re-upserting an existing key returns `"updated"`, leaves `count()` unchanged, overwrites the value in place, and preserves the other rows and their order after `commit()`; a file whose header does not exactly match the canonical header raises `DatabaseError` and leaves the file untouched (FR-012); a row whose `puzzle_type`/`puzzle_number` do not reconstruct raises `PuzzleParseError` (FR-004 edge). Print loaded keys and the offending header/row.
- [ ] T015 [US2] Write FAILING integration tests in `tests/integration/test_ingest.py`: ingesting the same season twice to the same CSV leaves the row count unchanged and the second `IngestSummary` has `added == 0`, `updated == total` (SC-003); a changed source value overwrites the matching row in place. Print both summaries.

### Implementation for User Story 2

- [ ] T016 [US2] Implement `round_from_type_and_number(puzzle_type, puzzle_number) -> str` in `src/wheeldb/models.py`, co-located with the `puzzle_type`/`puzzle_number` properties as their inverse (`Bonus Round`→`BR`, `Toss-Up`+N→`TN`, `Round`+N→`RN`; raise `PuzzleParseError` on an unrecognized pair). Full docstring (Principle VI). Pass T013.
- [ ] T017 [US2] Extend `CsvPuzzleStore.__init__` in `src/wheeldb/csv_storage.py` to load an existing file: read rows with the `csv` module, validate the header equals the canonical header exactly else raise `DatabaseError` (file untouched, FR-012), reconstruct each row's `(season, episode, round)` key via `round_from_type_and_number` (raise `PuzzleParseError` on a bad pair), and populate the insertion-ordered dict preserving file order. Pass T014/T015.

**Checkpoint**: Re-runs are idempotent and update in place; header-mismatch and bad-row are guarded. User Stories 1 AND 2 both pass.

---

## Phase 5: User Story 3 - Best-effort multi-season ingest to CSV (Priority: P2)

**Goal**: A season range to CSV writes every retrievable season to the one file, reports skipped/unparsed seasons exactly like the SQLite path, and leaves already-written seasons intact when a later one fails.

**Independent Test**: Ingest a multi-season range to CSV where one season's fixture is absent; confirm the present season's rows are in the file, the missing season is reported as skipped, and the summary matches the SQLite path for the same input.

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [ ] T018 [US3] Write FAILING integration tests in `tests/integration/test_ingest.py` using `RecordingFetcher` over several fixture seasons with the CSV format: (a) ingesting a range writes rows for every retrievable season to one CSV and `fetcher.requested` equals the in-range seasons (FR-008); (b) a season whose fixture is absent (`RetrievalError`) is reported in `IngestSummary.skipped` while the other seasons remain in the file (earlier seasons not lost — per-season atomic commit) and the summary/exit match the SQLite path; (c) a retrieved-but-tableless season is reported in `unparsed` and adds no rows. Print committed/skipped/unparsed seasons.

### Implementation for User Story 3

- [ ] T019 [US3] Run T018 and make it green. The `ingest_seasons` loop is store-agnostic and `CsvPuzzleStore.commit` rewrites the whole accumulated dict, so best-effort skip/unparsed/halt and earlier-season retention should already hold; if a gap surfaces (e.g. a later season's commit not preserving earlier ones), make the minimal fix in `src/wheeldb/csv_storage.py` (commit writes the full dict) or `src/wheeldb/ingest.py`. No new parsing path (FR-001). **Done when**: T018 is green and the full offline suite (incl. 001/002) shows no regression.

**Checkpoint**: Single-season and range CSV ingest both work; best-effort behavior matches the SQLite path. All user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and whole-suite validation.

- [ ] T020 [P] Update `README.md` with `wheeldb ingest <season|range> --format csv [--db PATH]`, the `.csv` naming rule (FR-002a), and a note that CSV output stays spoiler-free.
- [ ] T021 [P] Docstring/lint pass over `src/wheeldb/csv_storage.py`, the `models.py` addition, and the `ingest.py`/`cli.py` changes (Principle VI); run `py -m ruff check src tests` and resolve findings.
- [ ] T022 Run the full offline suite `py -m pytest -ra` and confirm green (including the existing 001/002 tests — integration across features, Principle III).
- [ ] T023 Execute the [quickstart.md](quickstart.md) validation scenarios (1–6) and confirm the Acceptance items.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: depends on Foundational. MVP.
- **User Story 2 (Phase 4)**: depends on Foundational; extends the US1 `CsvPuzzleStore` (adds existing-file load) — implement US1 first. Independently testable.
- **User Story 3 (Phase 5)**: depends on Foundational; relies on the US1 ingest store-selection + per-season transaction. Independently testable.
- **Polish (Phase 6)**: depends on all desired stories.

### Test-first ordering (within every story)

- The test task(s) MUST be written and observed FAILING before the implementation task in the same story (Principle III; enforced by the Write hook).
- Foundational: T002 (tests) before T003 (impl).
- US1: T004–T007 (tests) before T008–T012 (impl).
- US2: T013–T015 (tests) before T016–T017 (impl); T016 (`round_from_type_and_number`) before T017 (which uses it).
- US3: T018 (tests) before T019 (impl/verify).

### Story independence

- US1 is a complete MVP writing to a fresh CSV (and leaves the SQLite path unchanged).
- US2 adds idempotent re-ingestion (existing-file load + header/round validation) without breaking US1 — same `CsvPuzzleStore`, `__init__` extended.
- US3 verifies range + best-effort parity without breaking US1/US2 (store-agnostic loop).

---

## Parallel Opportunities

- **Setup**: T001 alone.
- **Foundational**: T002 (tests) before T003 (impl) — same file, sequential.
- **US1 tests**: T004 (`test_csv_storage.py`) and T005 (`test_csv_path.py`) are different files → `[P]`; T006/T007 share `test_ingest.py` → sequential with each other.
- **US1 impl**: T008 (`csv_storage.py`), T009/T010 (`cli.py`), T011 (`ingest.py`), T012 (`__init__.py`) — T009 and T010 share `cli.py` (sequential); the others touch different files.
- **US2 tests**: T013 (`test_models.py`) is `[P]` vs T014/T015 (`test_csv_storage.py` / `test_ingest.py`).
- **Polish**: T020 (`README.md`) and T021 (lint) are different files → `[P]`.

> Tasks editing the same file (e.g. T006/T007, T008/T017 in `csv_storage.py`, T009/T010 in `cli.py`) are NOT parallel.

### Parallel example — User Story 1 tests

```bash
# Author these two failing-test files together:
Task: "Write failing upsert/serialization tests in tests/unit/test_csv_storage.py"   # T004
Task: "Write failing .csv path-derivation tests in tests/unit/test_csv_path.py"        # T005
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (CSV container).
2. Phase 3 US1: single-season ingest to a fresh CSV; default stays SQLite; spoiler-free CLI.
3. **STOP and VALIDATE**: ingest a fixture season with `--format csv` into a temp file; confirm the header + one row per puzzle and special-character round-trip.
4. Demo: `wheeldb ingest 42 --format csv --from-dir tests/fixtures`.

### Incremental delivery

1. Setup + Foundational → CSV container ready.
2. US1 → single-season CSV ingest (MVP) → validate → demo.
3. US2 → idempotent re-ingestion (merge into existing file) → validate (re-run, no duplicates) → demo.
4. US3 → range + best-effort skip/unparsed → validate → demo.
5. Polish → docs + full-suite green.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- Every `src/wheeldb/` write is gated: confirm the relevant test is RED first, then implement to GREEN.
- Reuse, don't duplicate: the CSV path reuses `ingest_seasons`, `Puzzle` derivations, the JSON `flags` encoding, and the `errors` hierarchy (Principle IV) — the only new production file is `csv_storage.py`, plus additions to `models.py`, `ingest.py`, `cli.py`, `__init__.py`.
- No new third-party dependency (stdlib `csv` + `json`).
- Commit after each task or logical red→green pair.

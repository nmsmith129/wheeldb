---

description: "Task list for PowerPoint Puzzle Injection"
---

# Tasks: PowerPoint Puzzle Injection

**Input**: Design documents from `/specs/006-pptm-puzzle-injection/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: REQUIRED. Constitution Principle III (Test-First) is NON-NEGOTIABLE and
is enforced by the `PreToolUse(Write)` guard (`.claude/hooks/test_first_guard.py`),
which blocks writing a `src/wheeldb/` module unless a test referencing it is
currently FAILING. Every implementation task below is therefore preceded by a
failing-test task. Run `py -m pytest` and observe RED before writing source.

**Dependency note**: this feature reads the **SQLite** ingested store (feature 002,
on `main`). A CSV source (feature 005) is out of scope here until PR #5 merges — no
`--format` option is added in this feature. Tests ingest a fixture season into a
`tmp_path` SQLite store first.

**Numbering note**: per spec US1 acceptance scenario, an empty `games/` yields
`wof001.pptm` — numbering is the smallest unused integer in **1–999**, zero-padded
to three digits (spec, plan, research.md Decision 3, and data-model.md all agree).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, and Polish carry no story label)
- File paths are exact and repo-relative.

## Path Conventions

Single project: `src/wheeldb/` and `tests/` at repository root (matches 001/002/005).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The one-time slot-mapping discovery and test scaffolding the stories rely on.

- [ ] T001 **SPIKE (manual, one-time)**: Discover **stable, edit-resistant anchors** for the 8 slots per research.md Decision 4 — never positional indices. Enter unique sentinels per slot in PowerPoint, save, and diff `ppt/slides/*.xml` to (a) locate each slot's solution/category run and (b) determine whether its containing shape is uniquely named. Then choose the anchor flavor: **preferred** — prep the template once so each slot holds a content placeholder token (`{{PUZZLE_n_SOLUTION}}` / `{{PUZZLE_n_CATEGORY}}`) and commit that token-prepped template as the tool's template; **conditional** — if the slot shapes are already uniquely named, use `(slide part, shape name)` anchors with no prep. Record the chosen anchors as the static `SLOT_MAPPING` data and append the captured anchors + procedure notes to `research.md`. Not test-gated (discovery + data). **Blocks injection tasks T010/T012.**
- [ ] T002 [P] Add `games/` to `.gitignore`, and add a `template_pptm` fixture to `tests/conftest.py` that copies the repo's `WheelofFortune6.4.pptm` into a `tmp_path` so tests use a throwaway source package offline (the real template is treated read-only). Docstring the fixture in the existing conftest style.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The store read-query, the error type, and the macro-safe package engine every story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 [P] Write FAILING unit tests in `tests/unit/test_storage.py` for `PuzzleStore.puzzles_for_season(season)`: returns the season's rows as `Puzzle` objects (correct attributes + derived `puzzle_type`); returns `[]` for an absent season; covers all three types present. Print the per-type counts on failure (Principle V).
- [ ] T004 [P] Write FAILING unit tests in `tests/unit/test_pptx_inject.py` for the package engine: reading the `template_pptm` fixture and rewriting it with one part changed produces an output whose every other ZIP entry — including `ppt/vbaProject.bin` — is byte-identical to the template; writing refuses to clobber an existing output path; a failed write leaves no partial file. Print the list of parts that differ on failure.
- [ ] T005 Add `class GameError(WheelDBError)` with a docstring to `src/wheeldb/errors.py` (extends the existing hierarchy — Principle IV). Makes T004/T009 error paths importable.
- [ ] T006 Implement `PuzzleStore.puzzles_for_season(season) -> list[Puzzle]` in `src/wheeldb/storage.py` (reuse the existing row→`Puzzle` mapping; no new data path). Pass T003. (Add the parity method to `CsvPuzzleStore` only if/when the CSV source is in scope on this branch.)
- [ ] T007 Implement the macro-safe package engine in `src/wheeldb/pptx_inject.py` to pass T004: read all parts from a source `.pptm`, rewrite only specified parts, copy every other entry through byte-for-byte (preserving names/compression, incl. `ppt/vbaProject.bin`), write atomically (temp file then rename), and refuse to overwrite an existing target. Docstring every method (Principle VI).

**Checkpoint**: A season's puzzles can be read, and a package can be rewritten while preserving the VBA and all untouched parts. No puzzle text is injected yet.

---

## Phase 3: User Story 1 - Generate a ready-to-play game file (Priority: P1) 🎯 MVP

**Goal**: From a host-named season, select 4 Round / 3 Toss-Up / 1 Bonus Round puzzles (optionally seeded), fill the template's eight slots, and write `games/wof[N].pptm` (smallest unused three-digit number), leaving the template unchanged.

**Independent Test**: Run the CLI against an ingested fixture season; confirm `games/wof001.pptm` is created with the eight slots populated, the template is byte-unchanged, and the run is spoiler-free.

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [ ] T008 [P] [US1] Write FAILING unit tests in `tests/unit/test_gamegen.py` for `next_game_number(games_dir)`: empty dir → 1; an **absent** `games_dir` → 1 (and is created on generation, FR-002); `{1,2}` used → 3; gap `{1,3}` → 2; non-matching filenames ignored; all 1–999 used → `GameError`; the formatted name is zero-padded (`wof001.pptm`). Print the used set and chosen number.
- [ ] T009 [P] [US1] Write FAILING unit tests in `tests/unit/test_gamegen.py` for `select_puzzles(season, store, seed)`: returns a SlotPlan with 4 Round, 3 Toss-Up, 1 Bonus Round, eight distinct puzzles, each in the correct slot range; the **same season + same seed yields the identical selection** and different/no seed may differ (FR-012/SC-006). Print the selected (season, episode, round) keys per slot.
- [ ] T010 [US1] Write FAILING unit tests in `tests/unit/test_pptx_inject.py` for `inject_puzzles(template, out, slot_assignments)` (uses `SLOT_MAPPING` from T001): after injection, re-reading the eight anchored runs yields exactly the assigned solution + category text, including values with `&`/`<`/quotes (XML-escaped round-trip); the template is unchanged; and a missing anchor (a slot whose token/named shape is absent) raises `GameError` rather than misplacing text. **Edit-robustness**: against a template variant that adds an unrelated part/shape (simulating a user wheel edit), injection still resolves all eight anchors and the added part survives byte-for-byte in the output. Print expected vs read-back per slot.
- [ ] T011 [US1] Write FAILING integration test in `tests/integration/test_game.py`: ingest a fixture season into a `tmp_path` store, run `cli.main(["game", "<season>", "--db", <store>, "--seed", "7", "--games-dir", <tmp>])`; assert `wof001.pptm` is created, exit 0, stdout names the file + slot counts and contains NO solution/category text, and the template is byte-unchanged. Print exit code and stdout.

### Implementation for User Story 1

- [ ] T012 [US1] Implement `inject_puzzles(template_path, out_path, slot_assignments)` and the `SLOT_MAPPING` table in `src/wheeldb/pptx_inject.py` (build on the T007 engine; resolve each slot via its stable anchor — placeholder token or named shape, never a positional index — and set the solution + category run, XML-escaped; raise `GameError` on a missing anchor). Pass T010.
- [ ] T013 [US1] Implement `select_puzzles(...)`, `next_game_number(...)`, and `generate_game(season, *, store, games_dir, seed, template_path)` in `src/wheeldb/gamegen.py`: read via `puzzles_for_season`, group by `puzzle_type`, sample 4/3/1 without replacement using a local `random.Random(seed)`, assign to slots, **create `games_dir` if absent (FR-002)**, pick the next number, and write via `inject_puzzles`; return the created path. Pass T008/T009.
- [ ] T014 [US1] Add the `game` subcommand to `src/wheeldb/cli.py` (positional `season`; `--seed`, `--db`, `--games-dir` per contracts/cli.md — no `--format` in this feature); call `generate_game`; print the spoiler-free summary (file + slot counts) to stdout; map `GameError` and a bad argument to a clear stderr message and exit 2. Pass T011.
- [ ] T015 [US1] Export `generate_game`, `inject_puzzles`, and `GameError` from `src/wheeldb/__init__.py` (`__all__`) per [contracts/library-api.md](contracts/library-api.md).

**Checkpoint**: A single command generates a playable `games/wof[N].pptm` from a season; the template/VBA is untouched. MVP deliverable.

---

## Phase 4: User Story 2 - Players are not spoiled by the generation step (Priority: P1)

**Goal**: Nothing the tool prints (success or error) reveals a puzzle solution or category.

**Independent Test**: Inspect all operator output of a successful run and of an error run; confirm no solution/category text appears.

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [ ] T016 [US2] Write FAILING integration tests in `tests/integration/test_game.py`: (a) scan the full stdout **and** stderr of a successful generation against the known fixture-season solutions AND categories — none appear; (b) an error run (a season short on one type) writes an error naming only the type and counts, with no puzzle content, and exits 2. Print captured stdout/stderr.

### Implementation for User Story 2

- [ ] T017 [US2] Ensure `src/wheeldb/cli.py` (and `GameError` messages raised in `gamegen.py`) emit only file path, season, and counts — never solution or category text — including the insufficient-puzzles and season-absent errors (Decision 6/7). Pass T016.

**Checkpoint**: Generation is provably spoiler-free in both success and failure paths. US1 + US2 hold.

---

## Phase 5: User Story 3 - Correct puzzle types land in the correct slots (Priority: P2)

**Goal**: Slots 1–4 are Round, 5–7 are Toss-Up, 8 is Bonus Round; shortfalls error all-or-nothing.

**Independent Test**: Generate a seeded game and read back the eight slots; confirm the type-per-slot layout and eight distinct puzzles; confirm a season short on a type produces no file.

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [ ] T018 [US3] Write FAILING test in `tests/integration/test_game.py` (or `tests/unit/test_gamegen.py`): generate a seeded game, read back the eight mapped slots via the package, and assert slots 1–4 hold Round solutions, 5–7 hold Toss-Up, 8 holds Bonus Round, and the eight puzzles are distinct — matching the seeded `select_puzzles` plan. Print the slot→type readback.
- [ ] T019 [US3] Write FAILING unit tests in `tests/unit/test_gamegen.py`: a season with fewer than 4 Round / 3 Toss-Up / 1 Bonus puzzles raises `GameError` naming the short type and count and writes no file (all-or-nothing); an absent season raises `GameError`. Print the per-type availability.

### Implementation for User Story 3

- [ ] T020 [US3] In `src/wheeldb/gamegen.py`, validate per-type availability **before** writing (raise `GameError` on any shortfall or absent season) and enforce the slot→type assignment so each slot range receives only its type. Pass T018/T019. (Core selection exists from T013; this pins type-correctness and the all-or-nothing error.)

**Checkpoint**: Games follow the Round/Toss-Up/Bonus structure; insufficient data fails cleanly with no partial file. All stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and whole-suite validation.

- [ ] T021 [P] Update `README.md` with `wheeldb game <season> [--seed] [--db] [--games-dir]` usage, the `games/wof[N].pptm` naming rule, and notes that the template/VBA is preserved and generation is spoiler-free.
- [ ] T022 [P] Docstring/lint pass over `src/wheeldb/pptx_inject.py`, `src/wheeldb/gamegen.py`, and the `storage.py`/`cli.py`/`errors.py` additions (Principle VI); ensure no line exceeds the 100-char limit; run `py -m ruff check src tests` if ruff is available, else a manual check.
- [ ] T023 Run the full offline suite `py -m pytest -ra` and confirm green (including the existing 001/002 tests — integration across features, Principle III).
- [ ] T024 Execute the [quickstart.md](quickstart.md) validation scenarios (1–6) and confirm the Acceptance items.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: T001 spike is one-time and manual; T002 is independent. T001 blocks the injection tasks (T010/T012) but not storage/selection/numbering.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: depends on Foundational; injection (T010/T012) also depends on the T001 spike. MVP.
- **User Story 2 (Phase 4)**: depends on US1 (it constrains the CLI/error output US1 introduces). Independently testable.
- **User Story 3 (Phase 5)**: depends on US1's `select_puzzles`/injection; pins type-correctness + shortfall errors. Independently testable.
- **Polish (Phase 6)**: depends on all desired stories.

### Test-first ordering (within every story)

- Foundational: T003/T004 (tests) before T005–T007 (impl).
- US1: T008–T011 (tests) before T012–T015 (impl); T012 needs the T001 mapping.
- US2: T016 (test) before T017 (impl).
- US3: T018–T019 (tests) before T020 (impl).

### Story independence

- US1 is a complete MVP: a generated, playable game file.
- US2 hardens + proves the spoiler-free guarantee without changing the artifact.
- US3 pins the type→slot correctness and clean failure without breaking US1/US2.

---

## Parallel Opportunities

- **Setup**: T002 can proceed while the T001 spike is arranged (different artifacts).
- **Foundational tests**: T003 (`test_storage.py`) and T004 (`test_pptx_inject.py`) are different files → `[P]`. T005 (errors) is independent of T006/T007.
- **US1 tests**: T008 and T009 are both in `test_gamegen.py` (sequential with each other) but `[P]` vs T010 (`test_pptx_inject.py`); T011 is `test_game.py`.
- **US1 impl**: T012 (`pptx_inject.py`), T013 (`gamegen.py`), T014 (`cli.py`), T015 (`__init__.py`) touch different files — parallelizable once their tests are red, except T013 depends on T012 (inject) and T014 depends on T013.
- **Polish**: T021 (`README.md`) and T022 (lint) are different files → `[P]`.

> Tasks editing the same file (e.g. T008/T009 in `test_gamegen.py`, T004/T010 in `test_pptx_inject.py`) are NOT parallel.

### Parallel example — Foundational

```bash
# Author the two foundational failing-test files together:
Task: "Write failing puzzles_for_season tests in tests/unit/test_storage.py"   # T003
Task: "Write failing package-preservation tests in tests/unit/test_pptx_inject.py"  # T004
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup (incl. the T001 slot-mapping spike) → Phase 2 Foundational.
2. Phase 3 US1: season selection + slot injection + numbering + CLI.
3. **STOP and VALIDATE**: generate a game from an ingested fixture season; confirm
   `wof001.pptm`, the template byte-unchanged, and spoiler-free output.
4. Demo: `wheeldb game 42 --seed 7`.

### Incremental delivery

1. Setup + Foundational → engine + store query ready.
2. US1 → playable game (MVP) → validate → demo.
3. US2 → spoiler-free hardening → validate.
4. US3 → type→slot correctness + clean shortfall errors → validate.
5. Polish → docs + full-suite green.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- The T001 spike requires PowerPoint and a human; it produces the `SLOT_MAPPING`
  data the injector needs and cannot be done in CI. Sequence it first.
- Every `src/wheeldb/` write is gated: confirm the relevant test is RED first.
- Reuse, don't duplicate: selection reuses the store + `Puzzle` derivations; the new
  production files are `pptx_inject.py` and `gamegen.py`, plus additions to
  `storage.py`, `errors.py`, `cli.py`, `__init__.py` (Principle IV).
- No new third-party dependency (stdlib `zipfile`, `xml`/`re`, `random`).
- Commit after each task or logical red→green pair.

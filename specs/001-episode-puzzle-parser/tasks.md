# Tasks: Episode Puzzle Parser

**Input**: Design documents from `/specs/001-episode-puzzle-parser/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: REQUIRED for this feature. The constitution's Principle III (Test-First,
NON-NEGOTIABLE) mandates tests before implementation, and User Story 3 is itself
about test output. All test tasks below MUST be written and observed to FAIL
before the corresponding implementation task.

**Organization**: Tasks are grouped by user story. Note both US1 and US2 are
priority P1; together they form the MVP. US2 (the attribute-bearing parse core)
is implemented first because US1 (retrieval orchestration) builds on it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)
- Paths follow the single-project layout in plan.md (`src/wheeldb/`, `tests/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and test scaffolding

- [X] T001 Create project structure per plan.md: `src/wheeldb/` package dir (with empty `__init__.py`) and `tests/` tree (`tests/fixtures/`, `tests/unit/`, `tests/integration/`)
- [X] T002 Create `pyproject.toml` declaring Python 3.11+, dependencies `requests` + `beautifulsoup4`, dev dependency `pytest`, and a `wheeldb` console-script entry point `wheeldb = "wheeldb.cli:main"`
- [X] T003 [P] Configure linting/formatting (e.g. `ruff`) via `pyproject.toml` / config file at repo root
- [X] T004 [P] Capture representative season-page HTML fixtures for the three verified eras into `tests/fixtures/compendium1.html`, `tests/fixtures/compendium20.html`, `tests/fixtures/compendium42.html` (S42 must contain episode #8011 with its three puzzles)
- [X] T005 Create `tests/conftest.py` with a fixture-HTML loader, a fixture-backed `Fetcher` implementation (reads `tests/fixtures/compendium{N}.html`), and registration of a `--print-puzzles` pytest command-line option (rendering helper implemented in T022)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types depended on by every user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 [P] Define typed errors `RetrievalError` and `ParseError` (with docstrings) in `src/wheeldb/errors.py`
- [X] T007 [P] Define the `Fetcher` protocol (`get_season_html(season_number) -> str`, docstring per contracts/library-api.md) in `src/wheeldb/fetch.py`

**Checkpoint**: Error vocabulary and the fetch seam exist — story work can begin

---

## Phase 3: User Story 2 - Each puzzle carries its full, normalized attributes (Priority: P1)

**Goal**: Turn a season-page puzzle row into a `Puzzle` object whose six required
attributes (and derivations) are correctly normalized per FORMAT.md and the
clarifications (quotes stripped, symbols stripped, date ISO-or-raw, round = clean
code).

**Independent Test**: Parse fixture rows containing a quoted solution and an
annotated round (e.g. prize-puzzle `R3*`) and confirm the resulting `Puzzle` has
the solution without quotes, the round without the symbol, an ISO/raw date, and
all six attributes populated — entirely offline.

### Tests for User Story 2 (write FIRST, ensure they FAIL) ⚠️

- [X] T008 [P] [US2] Unit tests for normalization in `tests/unit/test_normalize.py`: quote stripping (straight + curly), category trim, date `M/D/YY`→ISO with year pivot (`>=83`→19xx) and raw-text retention when unparseable, `*`/`^` stripping off date/round, `#` stripping off episode — with debug output of input/expected/actual (Principle V)
- [X] T009 [P] [US2] Unit tests for the `Puzzle` model in `tests/unit/test_models.py`: six attributes present, `round_name`/`puzzle_type` derivations, `flags` population, and `(season, episode, round, solution)` uniqueness/equality
- [X] T010 [P] [US2] Unit tests for the parser in `tests/unit/test_parser.py` over fixtures: table selected by header signature (skips non-puzzle tables), one `Puzzle` per data row in source order, header row skipped, empty-PUZZLE row skipped, two rows differing only by a duplicated/malformed round label remain two distinct `Puzzle`s (spec Edge Cases), era coverage (S1/S20/S42)

### Implementation for User Story 2

- [X] T011 [P] [US2] Implement the single-source normalization functions (`normalize_solution`, `normalize_category`, `normalize_date`, `normalize_round`, `normalize_episode`, each docstring'd) in `src/wheeldb/normalize.py` (Principle IV — no normalization logic elsewhere)
- [X] T012 [P] [US2] Implement the `Puzzle` dataclass with six required attributes plus `round_name`/`puzzle_type` properties and `flags` in `src/wheeldb/models.py`; every method/property carries a docstring stating purpose, parameters, and return value (Principle VI)
- [X] T013 [US2] Implement `find_puzzle_table` (header-signature selection) and `parse_rows` in `src/wheeldb/parser.py`, consuming `normalize.py` and `models.py`; every method carries a docstring stating purpose, parameters, and return value (Principle VI) (depends on T011, T012)

**Checkpoint**: Raw season HTML → correctly-attributed `Puzzle` objects, verified offline across all three eras

---

## Phase 4: User Story 1 - Retrieve all puzzles for an episode (Priority: P1) 🎯 MVP

**Goal**: Given an episode number, search compendium season pages, match the `EP#`
column, and return every puzzle for that episode (ordered by round), with
not-found yielding an empty list and retrieval failure raising `RetrievalError`.

**Independent Test**: `extract_episode(8011)` against the S42 fixture returns the
three known puzzles with correct season/episode/round/order; a non-existent
episode returns `[]`; a simulated HTTP 403 raises `RetrievalError`.

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [X] T014 [P] [US1] Integration tests for `extract_episode` in `tests/integration/test_extract_episode.py`: S42 #8011 → exactly 3 puzzles (`OPENING NIGHT`/T1, `ANIMATED SHORT ATTENTION SPAN`/R2, `DIGITAL FOOTPRINT`/BR) with season 42; cross-era episode from S1/S20; non-existent episode → `[]`; uses the fixture-backed `Fetcher`
- [X] T015 [P] [US1] Unit tests for the live fetcher in `tests/unit/test_fetch.py` (HTTP mocked): sends a real browser `User-Agent`, honors a politeness delay, and maps HTTP 403/non-200 to `RetrievalError`
- [X] T016 [P] [US1] CLI tests in `tests/integration/test_cli.py`: stdout reports count + season + round codes + source URL and contains NO puzzle solution text (Principle II / FR-013); not-found exits 0; retrieval failure exits non-zero with stderr message

### Implementation for User Story 1

- [X] T017 [US1] Implement the live HTTP `Fetcher` (browser `User-Agent`, politeness delay, 403/non-200 → `RetrievalError`) in `src/wheeldb/fetch.py`; every method carries a docstring stating purpose, parameters, and return value (Principle VI)
- [X] T018 [US1] Implement `extract_episode` in `src/wheeldb/episodes.py`: search season pages, match normalized `EP#`, short-circuit once the containing season is found/passed, preserve round order, return `[]` when unmatched, propagate `RetrievalError`; every method carries a docstring stating purpose, parameters, and return value (Principle VI) (depends on T013, T017)
- [X] T019 [US1] Implement the spoiler-free CLI (`argparse` `episode <N>` subcommand; counts/provenance to stdout, diagnostics/errors to stderr; never prints solutions) in `src/wheeldb/cli.py`; every method carries a docstring stating purpose, parameters, and return value (Principle VI) (depends on T018)
- [X] T020 [US1] Export `extract_episode` and `Puzzle` from `src/wheeldb/__init__.py` (depends on T018, T012)

**Checkpoint**: Episode number → puzzles works end-to-end offline; CLI is spoiler-free. **MVP complete (US2 + US1).**

---

## Phase 5: User Story 3 - Print puzzles during testing (Priority: P2)

**Goal**: Provide a test-only option to print parsed puzzles (including solutions)
in a readable form, while guaranteeing solutions never print in normal operation.

**Independent Test**: Run the integration test with `--print-puzzles` and confirm
each puzzle's attributes (incl. solution) appear in the test log; run without it
and confirm no solution text appears.

### Tests for User Story 3 (write FIRST, ensure they FAIL) ⚠️

- [X] T021 [P] [US3] Tests in `tests/integration/test_print_option.py`: with `--print-puzzles` set, each puzzle's six attributes incl. solution are printed; without it, captured output contains no solution text (asserts the spoiler boundary)

### Implementation for User Story 3

- [X] T022 [US3] Implement the puzzle-printing helper (renders each `Puzzle`'s attributes incl. solution) invoked only when `--print-puzzles` is set, wired in `tests/conftest.py` (depends on T005); confirm no `src/wheeldb/` code path calls it
- [X] T023 [US3] Add Principle V debug output (inputs/expected/actual at assertion points) to the test suite where not already present

**Checkpoint**: All user stories independently functional; spoiler boundary verified

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Constitution-driven quality gates across the feature

- [X] T024 [P] Docstring verification (Principle VI): confirm every method/function in `src/wheeldb/` carries the docstring required by its implementation task (purpose, each parameter, return value) — a final check, not a catch-up
- [X] T025 [P] Reuse review (Principle IV): confirm all normalization flows through `src/wheeldb/normalize.py` with no duplicated parsing/normalization logic
- [X] T026 [P] Add usage documentation (library + CLI) to `README.md`, referencing contracts and the spoiler-free behavior
- [X] T027 Run the `quickstart.md` validation end-to-end: offline `pytest`, `pytest --print-puzzles`, and the CLI spoiler-free stdout check

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all stories
- **US2 (Phase 3)**: Depends on Foundational — provides the parse→Puzzle core
- **US1 (Phase 4)**: Depends on Foundational AND US2 (consumes `parser.py`) — together with US2 forms the MVP
- **US3 (Phase 5)**: Depends on Foundational; exercises US1/US2 output but is independently testable
- **Polish (Phase 6)**: Depends on all desired stories being complete

### User Story Dependencies

- **US2 (P1)**: Independently testable (parse fixtures → attributes). First of the P1 pair.
- **US1 (P1)**: Independently testable at the behavior level (`extract_episode` over fixtures), but its implementation consumes US2's parser — implement US2 first.
- **US3 (P2)**: Independently testable; needs at least one of US1/US2 producing puzzles to print.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Principle III)
- normalize + model before parser; parser before retrieval; retrieval before CLI

### Parallel Opportunities

- Setup: T003 + T004 in parallel
- Foundational: T006 + T007 in parallel
- US2 tests T008/T009/T010 in parallel; impl T011 + T012 in parallel (T013 after both)
- US1 tests T014/T015/T016 in parallel
- Polish: T024/T025/T026 in parallel

---

## Parallel Example: User Story 2

```bash
# Tests first (parallel — different files):
Task: "Unit tests for normalization in tests/unit/test_normalize.py"
Task: "Unit tests for the Puzzle model in tests/unit/test_models.py"
Task: "Unit tests for the parser in tests/unit/test_parser.py"

# Then implementation (T011 + T012 parallel; T013 depends on both):
Task: "Implement normalization in src/wheeldb/normalize.py"
Task: "Implement the Puzzle dataclass in src/wheeldb/models.py"
```

---

## Implementation Strategy

### MVP (the P1 pair: US2 + US1)

1. Phase 1 Setup → Phase 2 Foundational
2. Phase 3 US2 (parse → attributed `Puzzle`) — STOP and validate offline
3. Phase 4 US1 (`extract_episode` + spoiler-free CLI) — STOP and validate against #8011
4. This is a demoable MVP: episode number → puzzles, fully offline-tested

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US2 → validate attribute correctness across eras
3. US1 → validate retrieval + CLI (MVP!)
4. US3 → add the test-only print option, verify spoiler boundary
5. Polish → constitution quality gates + quickstart validation

---

## Notes

- [P] = different files, no incomplete dependencies
- Verify every test FAILS before its implementation task (Principle III)
- No `src/wheeldb/` code path may print puzzle solutions (Principle II); solutions
  surface only via the test-only print helper (T022)
- Commit after each task or logical group

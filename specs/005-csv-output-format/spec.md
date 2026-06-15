# Feature Specification: CSV Output Format

**Feature Branch**: `005-csv-output-format`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "Add code such that the CLI argument \"--csv\" saves the scraped puzzles as a .csv file rather than a .SQLite file. Use the same naming scheme for the .csv files that is already used by the .SQLite files. Edits should replace the puzzles in question with their new versions, keeping the rest of the puzzles as-is. The order of saved data in a .csv row should be: season,episode,date,puzzle_type(),puzzle_number(),category,solution"

**Resolved direction** (from clarification): the output format is selected via a
`--format {sqlite,csv}` option on the ingest command, defaulting to `sqlite`. A CSV
row carries the user-requested fields in order — `season, episode, date, puzzle_type,
puzzle_number, category, solution` — followed by a trailing `flags` cell so annotations
round-trip. The CSV file has no `round` column; the stable identity used to replace a
puzzle in place, `(season, episode, round)`, is reconstructed from `puzzle_type` and
`puzzle_number` when reading existing rows. Idempotency, added/updated counts, and
best-effort per-season behavior match the SQLite path exactly.

## Clarifications

### Session 2026-06-15

- Q: How is the CSV output path determined when `--format csv` is selected? → A: Reuse the existing `--db PATH`; write to the same path with its extension replaced by `.csv` (default becomes `wheeldb.csv`), appending `.csv` if the path has no recognized extension.
- Q: What happens when a pre-existing CSV file's header/columns don't match the expected layout? → A: Require an exact header match; a mismatch (wrong order, missing/extra columns) is a clear halting error that leaves the file untouched.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest puzzles to a CSV file (Priority: P1)

A user runs the ingest command and asks for the output to be written as a CSV
file instead of the SQLite database, so they can open the puzzle data in a
spreadsheet or feed it to tools that consume plain text tables.

**Why this priority**: This is the core of the feature — without the ability to
direct ingest output to a CSV file, nothing else matters. It is the MVP.

**Independent Test**: Run an ingest of one season against saved fixtures with the
CSV output format selected, then open the resulting file and confirm it contains
one row per puzzle with the expected columns and values.

**Acceptance Scenarios**:

1. **Given** no output file exists yet, **When** the user ingests a season with
   the CSV format selected, **Then** a CSV file is created containing a header row
   and one data row per puzzle of that season.
2. **Given** the CSV format is selected, **When** the run completes, **Then** the
   command's summary reports the same counts (added, updated, total, skipped,
   unparsed) it would report for the same data written to the database.
3. **Given** the user does not specify a format, **When** they ingest, **Then**
   the output is written to the SQLite database exactly as before (no behavior
   change for existing users).

---

### User Story 2 - Re-ingest is idempotent (Priority: P1)

A user ingests the same season twice (or overlapping seasons) into the same CSV
file and expects the file to remain a clean, de-duplicated dataset — the second
run updates existing puzzles in place rather than appending duplicate rows.

**Why this priority**: Idempotency is a project-wide guarantee (the SQLite path
already provides it). A CSV output that duplicated rows on re-run would be a
regression against established behavior and would make the file untrustworthy.

**Independent Test**: Ingest a season to CSV, then ingest the same season again
to the same file; confirm the file has the same number of data rows after the
second run as after the first, and that changed source values overwrite the
prior values for the matching puzzle.

**Acceptance Scenarios**:

1. **Given** a CSV file already containing a season's puzzles, **When** the user
   ingests the same season again, **Then** the file still has exactly one row per
   unique puzzle (no duplicates) and the row count is unchanged.
2. **Given** a puzzle already in the CSV file, **When** the same puzzle is
   ingested again with a changed value (e.g. a corrected category), **Then** the
   existing row is updated in place and the run counts it as "updated", not
   "added".
3. **Given** a brand-new puzzle not yet in the file, **When** it is ingested,
   **Then** a new row is added and the run counts it as "added".

---

### User Story 3 - Best-effort multi-season ingest to CSV (Priority: P2)

A user ingests a range of seasons to CSV where some seasons cannot be retrieved
or contain no recognizable puzzle data, and expects the same best-effort outcome
as the database path: retrievable seasons are written, problem seasons are
reported and skipped, and a data error halts the run leaving already-written
seasons intact.

**Why this priority**: Range ingestion and best-effort behavior already exist;
the CSV path must not silently behave differently. It is P2 because single-season
CSV output (P1) already delivers standalone value.

**Independent Test**: Ingest a range to CSV where one season's fixture is missing
and another is present; confirm the present season's puzzles are in the file, the
missing season is reported as skipped, and the summary matches the database path.

**Acceptance Scenarios**:

1. **Given** a requested season cannot be retrieved, **When** ingesting a range
   to CSV, **Then** that season is reported as skipped and the other seasons are
   still written to the file.
2. **Given** a retrieved season contains no recognizable puzzle data, **When**
   ingesting to CSV, **Then** that season is reported as unparsed and does not
   add rows.

---

### Edge Cases

- **Empty / first run**: ingesting to a CSV path that does not yet exist creates
  the file with a header row; ingesting zero puzzles still yields a valid file
  with just the header.
- **Multi-valued flags**: a puzzle carrying annotation flags is stored as a
  single trailing cell so the row stays one line and re-import preserves the flags
  exactly.
- **Round reconstruction**: a puzzle whose `puzzle_type`/`puzzle_number` pair does
  not map back to a recognizable round code is treated as a data error consistent
  with the SQLite path (the run halts on the offending season), not silently
  mismatched against the wrong row.
- **Embedded separators / special characters**: solutions or categories
  containing commas, quotes, or newlines are written so they round-trip back to
  the identical value on re-read (no row corruption, no field splitting).
- **Pre-existing file from a prior run**: re-running merges against the existing
  file's contents rather than overwriting blindly, so earlier seasons are not lost
  when a later season is ingested to the same file.
- **Pre-existing file with a mismatched header**: if the existing CSV's header does
  not exactly match the expected columns (wrong order, missing or extra columns),
  the run halts with a clear error and leaves the file untouched rather than
  appending misaligned rows.
- **Interrupted/failed write within a season**: a data error while writing a
  season leaves the file as it was before that season (the season's partial work
  is not left half-written), consistent with the all-or-nothing per-season
  behavior of the database path.
- **Format selection**: an unrecognized format value is rejected with a clear
  error rather than silently falling back.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow the user to choose, at ingest time, whether
  puzzle output is written to the SQLite database or to a CSV file.
- **FR-002**: When no output format is chosen, the system MUST write to the
  SQLite database, preserving the current default behavior unchanged.
- **FR-002a**: The CSV output path MUST be derived from the existing database path
  argument: when CSV is selected, the system writes to that same path with its
  extension replaced by `.csv` (so the default `wheeldb.sqlite` becomes
  `wheeldb.csv`), appending `.csv` if the provided path has no recognized extension.
- **FR-003**: The CSV output MUST contain a header row and one data row per
  puzzle, with columns in this exact order: `season`, `episode`, `date`,
  `puzzle_type`, `puzzle_number`, `category`, `solution`, `flags`. The first seven
  columns are the user-requested fields in the requested order; `flags` is a
  trailing column so annotations are preserved (FR-006). The `round` code is NOT a
  column — it is reconstructed when needed (FR-004).
- **FR-004**: Re-ingesting MUST keep the CSV file de-duplicated and updated in
  place, keyed on the stable identity of a puzzle (season, episode, round): an
  existing puzzle is overwritten with its new version, a new puzzle is appended, and
  all other puzzles are left as-is. Because the CSV has no `round` column, the round
  code MUST be reconstructed from `puzzle_type` + `puzzle_number` (Toss-Up + N →
  `TN`, Round + N → `RN`, Bonus Round → `BR`) to determine the stable identity of an
  existing row.
- **FR-005**: The system MUST classify each written puzzle as either newly added
  or updated, and the run summary MUST report added, updated, total, skipped, and
  unparsed counts identically to the SQLite path for the same input.
- **FR-006**: Annotation flags MUST be preserved across write and subsequent
  re-read so that a round-trip does not lose or alter them, stored within a single
  field of the row.
- **FR-007**: Field values containing separators or special characters MUST be
  written and read back without corrupting the row or altering the value.
- **FR-008**: Multi-season ingest to CSV MUST be best-effort per season: an
  unretrievable season is reported and skipped, a retrieved-but-empty season is
  reported as unparsed, and a data error halts the run while leaving
  already-written seasons intact.
- **FR-009**: Writing a single season's puzzles MUST be all-or-nothing: if the
  season cannot be fully written, the file MUST be left in its prior state for
  that season rather than partially updated.
- **FR-010**: The CSV output path MUST NOT print puzzle solutions during normal
  operation; only counts and provenance are reported, consistent with the
  no-spoilers rule.
- **FR-011**: Selecting an output format that is not supported MUST produce a
  clear error and a non-success exit, not a silent fallback.
- **FR-012**: When merging into a pre-existing CSV file, the system MUST verify the
  file's header exactly matches the expected column set and order; a mismatch
  (wrong order, missing, or extra columns) MUST halt the run with a clear error and
  leave the file untouched rather than appending misaligned rows.

### Key Entities *(include if feature involves data)*

- **Puzzle record**: one Wheel of Fortune puzzle from one round of one episode,
  identified uniquely by (season, episode, round). Carries solution, category,
  air date, derived puzzle number and type, and annotation flags. This is the
  same record the database stores; the CSV format is an alternative container that
  serializes it as `season, episode, date, puzzle_type, puzzle_number, category,
  solution, flags` and reconstructs the round code from type + number on read.
- **CSV output file**: a plain-text table of puzzle records with a header row.
  Acts as the alternative persistence target to the SQLite database; it is read,
  merged, and rewritten on each unit of work so it stays de-duplicated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can produce a CSV of a season's puzzles in a single ingest
  command without any manual post-processing.
- **SC-002**: Ingesting the same data to CSV and to the database yields the same
  reported counts (added, updated, total, skipped, unparsed) in 100% of runs.
- **SC-003**: Re-ingesting an already-ingested season to the same CSV file leaves
  the data-row count unchanged (zero duplicate rows introduced) in 100% of runs.
- **SC-004**: Every stored field — including flags and values containing commas,
  quotes, or newlines — round-trips back to its exact original value when the file
  is re-read, with zero data-corruption incidents in the test suite.
- **SC-005**: Existing users who do not select a format observe no change in
  behavior or output location.

## Assumptions

- The CSV output is selected per ingest run via the existing ingest command; the
  episode-lookup command is not required to read from CSV in this feature.
- The CSV output file is named using the same scheme the SQLite store uses today:
  the output location is taken from the same database path argument, with its
  extension replaced by `.csv` (e.g. the default `wheeldb.sqlite` → `wheeldb.csv`);
  a path with no recognized extension has `.csv` appended (see FR-002a).
- One CSV file holds all ingested puzzles (across seasons), mirroring how one
  SQLite database holds all puzzles; the output location is provided the same way
  the database path is today.
- The CSV column set is the user-requested ordered fields (`season, episode, date,
  puzzle_type, puzzle_number, category, solution`) plus a trailing JSON-encoded
  `flags` column; `puzzle_type`/`puzzle_number` are the derived values the model
  already exposes, and the `round` code is not stored as its own column.
- The stable identity for de-duplication is (season, episode, round), matching the
  database's primary key, even though uniqueness elsewhere also considers the
  solution. For the CSV path the round code is reconstructed from `puzzle_type` and
  `puzzle_number` (the inverse of how the model derives them) to recover this
  identity from a stored row.
- "Full parity" means observable behavior parity (idempotency, counts,
  best-effort, all-or-nothing per season, no spoilers), not byte-for-byte file
  equivalence between the two formats.
- The offline test suite (saved fixtures) remains the source of truth for
  verifying parity; no live network access is required to validate this feature.
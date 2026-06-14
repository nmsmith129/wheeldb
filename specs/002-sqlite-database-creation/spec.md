# Feature Specification: SQLite Puzzle Database

**Feature Branch**: `002-sqlite-database-creation`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "We need to make an SQLite database of Wheel of Fortune puzzles. This code must utilize the existing parser to get puzzles which it can add to new entries in the database, and each puzzle should store all of its attributes as well as its puzzle_number() and puzzle_type(). Each puzzle should be one row."

## Clarifications

### Session 2026-06-14

- Q: When a puzzle's round code yields no derivable puzzle number/type, what should ingestion do? → A: Abort the whole ingest run as a data error (write nothing).
- Q: On re-ingestion, what happens to previously stored puzzles absent from the new parse? → A: Additive by default — insert/update only, never delete; pruning occurs only when explicitly requested.
- Q: How may the maintainer invoke ingestion? → A: Only by supplying a single season (e.g. "40") or a season range (e.g. "37-40"); the scraper looks exclusively at the supplied season(s). There is no episode-based or all-seasons ingest entry point.
- Q: In a range, if one season fails to retrieve, should the whole run abort or proceed? → A: Best-effort, per-season. Each season commits independently; a season that fails to retrieve is reported and skipped while the other seasons still commit. (A data error within a season still rolls back that season and halts the run; seasons already committed are kept.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest a single season into a queryable database (Priority: P1)

A maintainer runs the ingest command with one season number (e.g. `40`) and
saves that season's puzzles into a local puzzle database, so the puzzles become
permanently queryable instead of being printed once and lost. The scraper looks
**exclusively** at the supplied season; the puzzles are obtained through the
existing season-parsing capability, and each puzzle is stored as its own record
carrying every attribute the puzzle exposes, including its derived puzzle number
and puzzle type.

**Why this priority**: This is the core of the feature — without the ability to
turn one season's parsed puzzles into stored rows there is no database. It
delivers the headline value (a persistent, queryable collection of puzzles) on
its own.

**Independent Test**: Run the ingest action with a single season against a
fixture-backed source and confirm the database afterward contains one row per
parsed puzzle for that season, each row carrying the correct attribute values and
the correct derived puzzle number and puzzle type.

**Acceptance Scenarios**:

1. **Given** an empty database and a season that parses to N puzzles, **When** the maintainer ingests that season, **Then** the database contains exactly N puzzle rows, all bearing that season number.
2. **Given** an ingested puzzle, **When** its stored row is inspected, **Then** the row holds the puzzle's solution, category, date, season, episode, and round, plus its derived puzzle number and puzzle type.
3. **Given** a season that parses to zero puzzles, **When** the maintainer ingests it, **Then** the action completes successfully and adds no rows.
4. **Given** a single season is requested, **When** ingestion runs, **Then** no season page other than the requested one is retrieved.

---

### User Story 2 - Idempotent re-ingestion (Priority: P2)

A maintainer re-ingests a season that was already stored — for example after a
correction upstream or simply by re-running the command. The database keeps a
single record per puzzle: previously stored puzzles are updated in place rather
than duplicated, so the collection never accumulates duplicate rows for the same
puzzle.

**Why this priority**: A puzzle database that doubles its rows on every re-run is
not trustworthy. Idempotency is required by the project's idempotent-runs
constraint and is what makes routine re-ingestion safe, but it builds on the P1
ability to store rows at all.

**Independent Test**: Ingest the same fixture-backed season twice and confirm
the row count after the second run equals the row count after the first, with no
duplicated puzzles.

**Acceptance Scenarios**:

1. **Given** a season already fully ingested, **When** the maintainer ingests the same season again, **Then** the total number of rows is unchanged.
2. **Given** a stored puzzle whose source attributes have changed upstream, **When** its season is re-ingested, **Then** the existing row reflects the new attribute values rather than a second row being created.

---

### User Story 3 - Ingest a season range in one run (Priority: P3)

A maintainer populates the database for several consecutive seasons in one action
by supplying a season range (e.g. `37-40`), so that every puzzle on each season
page in that inclusive range becomes a stored row. The scraper looks exclusively
at the seasons within the supplied range.

**Why this priority**: Range ingestion is the efficient way to build up the
collection across many seasons, but it is an extension of single-season ingestion
(P1) plus idempotency (P2) and is not required for the feature to deliver its
core value.

**Independent Test**: Ingest a fixture-backed range spanning several seasons and
confirm the database contains one row for every puzzle parsed from each season in
the inclusive range, and none from seasons outside it.

**Acceptance Scenarios**:

1. **Given** a range `37-40` whose four season pages parse to M puzzles in total, **When** the maintainer ingests that range, **Then** the database contains M puzzle rows spanning seasons 37 through 40 inclusive.
2. **Given** a range already ingested, **When** the same range is ingested again, **Then** no duplicate rows are created.
3. **Given** a range `37-40` is requested, **When** ingestion runs, **Then** no season page outside 37–40 is retrieved.
4. **Given** a range `37-40` where season 38 cannot be retrieved, **When** the maintainer ingests that range, **Then** seasons 37, 39, and 40 are committed, season 38 is reported as skipped, and the run exits non-zero.

---

### Edge Cases

- **Round code with no derivable number/type**: a puzzle whose round code is not a recognized toss-up, numbered round, or bonus round cannot yield a puzzle number. This is treated as a data error: the season containing it is rolled back (none of that season's rows are written) and the run **halts** — no further seasons in a range are processed — so the maintainer can investigate the unexpected round code rather than silently storing a partial season. Seasons committed earlier in the same range are retained. For a single-season request this means the database is left unchanged.
- **Malformed season argument**: an argument that is neither a single season number nor a `start-end` range (e.g. empty, non-numeric, or otherwise malformed) is rejected with a usage message before any retrieval or write occurs.
- **Reversed or single-value range**: a range whose start exceeds its end (e.g. `40-37`) is rejected; a range whose start equals its end (e.g. `40-40`) is accepted and behaves like the single season `40`.
- **Season outside the available range**: a requested season for which no source page exists is reported and skipped, without aborting the other requested seasons in a range and without corrupting the database.
- **Duplicate stable key within a single ingest**: if two parsed puzzles resolve to the same stable identity in one run, the database must still end with a single row for that identity rather than failing.
- **Source retrieval failure (best-effort range)**: if a requested season's page cannot be retrieved, that season is reported and skipped and the run continues with the remaining seasons; seasons that retrieve and parse cleanly are still committed. Each season is written atomically (all of its rows or none), so no individual season is left half-written. The run exits non-zero when any season was skipped. For a single-season request, a retrieval failure simply leaves the database unchanged.
- **Re-ingest with fewer puzzles than before**: if a season now parses to fewer puzzles than a previous ingest, the previously stored, now-absent puzzles are left in place (see Assumptions / FR-007a).
- **First run against a missing database file**: ingesting when no database yet exists must create the database and its structure rather than failing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST obtain puzzles to store through the project's existing puzzle-parsing capability, not through a new or duplicate parsing path.
- **FR-002**: System MUST store each obtained puzzle as exactly one row in the SQLite database.
- **FR-003**: Each stored row MUST record all of the puzzle's attributes: solution, category, date, season, episode, and round.
- **FR-004**: Each stored row MUST additionally record the puzzle's derived puzzle number and derived puzzle type.
- **FR-005**: System MUST create the SQLite database and its structure automatically when it does not already exist, so a first run needs no manual setup.
- **FR-006**: System MUST identify each puzzle by a stable key so the same puzzle can be recognized across runs.
- **FR-007**: Re-ingesting a puzzle that is already stored MUST update the existing row in place and MUST NOT create a duplicate row (idempotent runs).
- **FR-007a**: Re-ingestion MUST be additive by default — puzzles previously stored but absent from a later parse of the same episode/season MUST be left in place. The system MUST NOT delete such rows unless deletion is explicitly requested by the maintainer.
- **FR-008**: System MUST accept exactly two invocation forms for ingestion: a single season (e.g. `40`) or an inclusive season range (e.g. `37-40`). It MUST reject any other form (empty, non-numeric, or otherwise malformed) with a usage message and without retrieving or writing anything.
- **FR-008a**: System MUST confine the scraper to exactly the supplied season(s): only the requested season — or only the seasons within the requested inclusive range — may be retrieved. No episode-based ingest entry point and no implicit all-seasons sweep may exist.
- **FR-008b**: System MUST treat a range whose start equals its end as the single corresponding season, and MUST reject a range whose start is greater than its end.
- **FR-008c**: System MUST ingest the puzzles of a single season (supports User Story 1; parsing reuse per FR-001).
- **FR-008d**: System MUST ingest the puzzles of every season in a supplied inclusive range (supports User Story 3; parsing reuse per FR-001).
- **FR-009**: System MUST report the outcome of an ingest run — how many puzzles were added and updated, the season(s) committed, any season(s) skipped, and the provenance of the data — without printing any puzzle solution to normal output (spoiler-free), consistent with the project's CLI principle.
- **FR-010**: When a puzzle's derived number cannot be determined, the system MUST treat it as a data error: roll back the season containing it (write none of that season's rows), halt the run (process no further seasons), report the offending round code, and exit non-zero. Seasons committed earlier in the same range are retained; for a single-season request this leaves the database unchanged.
- **FR-011**: When a requested season's source cannot be retrieved, the system MUST report and skip that season and MUST continue processing the remaining requested seasons (best-effort). Seasons that retrieve and parse cleanly MUST still be committed; the run MUST exit non-zero when any season was skipped.
- **FR-011a**: Each season MUST be written atomically — all of that season's rows commit together or none do — so no individual season is ever left half-written, regardless of how many seasons a range contains.

### Key Entities *(include if feature involves data)*

- **Puzzle record**: one stored Wheel of Fortune puzzle. Holds the puzzle's solution, category, air date, season number, episode number, and round code, plus the derived puzzle number and puzzle type. Identified by a stable key composed of the attributes that make a puzzle unique within the collection (its season, episode, and round). One puzzle record corresponds to exactly one database row.
- **Puzzle database**: the SQLite store that holds all puzzle records. It is the durable product of the feature and is expected to grow as more episodes and seasons are ingested. It is unique on each record's stable key so that re-ingestion maintains rather than duplicates content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After ingesting a season that parses to N puzzles into an empty database, the database contains exactly N puzzle rows.
- **SC-002**: Every stored row exposes all six source attributes plus the derived puzzle number and puzzle type, with values matching what the parser produced for that puzzle (verifiable for 100% of stored rows).
- **SC-003**: Ingesting the same season twice results in the same number of rows as ingesting it once (zero duplicate rows on re-run).
- **SC-004**: A normal ingest run produces no puzzle solution in its standard output (0 spoilers leaked).
- **SC-005**: An ingest run against an absent database file succeeds and produces a usable database without any manual setup step.
- **SC-006**: When a puzzle's derived number cannot be determined, the season containing it writes zero rows and the run halts reporting the offending round code; for a single-season request the database is left unchanged.
- **SC-007**: Ingestion is invocable only with a single season or an inclusive season range; every other argument form is rejected with a usage message and writes zero rows.
- **SC-008**: For any single-season or range request, the only season pages retrieved are those the request names — 0 pages outside the requested season(s) are fetched.
- **SC-009**: In a range where some seasons retrieve cleanly and one cannot be retrieved, every cleanly-parsed season's rows are committed, the unretrievable season contributes zero rows, the skipped season is reported, and the run exits non-zero.
- **SC-010**: No individual season is ever left partially written: each season's row set is committed all-or-nothing.

## Assumptions

- **Ingestion is driven through the existing CLI**, extending the current command-line tool with an action to store puzzles, consistent with the project's CLI-interface principle. The action's only argument is a single season (`40`) or an inclusive season range (`37-40`). The existing read-only `episode` lookup command is separate and unchanged.
- **A range is inclusive of both endpoints and ascending**; `37-40` covers seasons 37, 38, 39, and 40. Ingestion is **best-effort per season** (FR-011/FR-011a): each season commits on its own, any season that cannot be retrieved is reported and skipped while the others still commit, and the run exits non-zero if any season was skipped. A *data error* (an unrecognized round code) is different — it rolls back its season and halts the run (FR-010), because it signals unexpected markup the maintainer should investigate rather than a merely missing page. Because the existing fetch layer cannot distinguish "page absent" from "blocked/network error," both are treated as a skip.
- **The stable identity of a puzzle is its (season, episode, round)** — the same identity the existing model already exposes as its puzzle identifier. This is assumed sufficient to make a puzzle unique within the collection.
- **The database file defaults to `wheeldb.sqlite` in the current working directory**, with the path overridable (e.g. a `--db` option); choosing a non-default path is a convenience, not a core requirement of this feature.
- **The puzzle's preserved annotation flags are stored alongside the other attributes** as part of "all of its attributes," in whatever form keeps one puzzle to one row.
- **Re-ingestion is additive/updating by default, not pruning**: puzzles previously stored but absent from a later parse of the same episode/season are left in place (not deleted), since their absence may reflect transient upstream markup changes rather than genuine removal. Pruning previously stored rows happens only when the maintainer explicitly requests it; defining that explicit-deletion interface in detail is out of scope for this feature (see FR-007a).
- **The data obtained from the parser is trusted as-is**; this feature does not re-validate or re-normalize puzzle attributes beyond what the existing parser already guarantees.
- **Scope excludes** querying/reporting tools beyond the run summary, schema migration of an existing database to new shapes, and any concurrent/multi-writer access patterns.

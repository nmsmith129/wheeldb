# Phase 1 Data Model: SQLite Puzzle Database

Derived from the spec's Key Entities, Functional Requirements, the three
clarifications, and the existing `Puzzle` value object (`models.py`). This feature
adds **persistence**; the in-memory `Puzzle` shape is unchanged and reused.

## Table: `puzzles`

One row per Wheel of Fortune puzzle (FR-002). Columns hold the puzzle's six source
attributes (FR-003), the two derived values (FR-004), and the preserved
annotation flags.

| Column | SQLite type | Null? | Source | Notes |
|--------|-------------|-------|--------|-------|
| `season` | INTEGER | NOT NULL | `Puzzle.season` | Part of primary key. |
| `episode` | INTEGER | NOT NULL | `Puzzle.episode` | Part of primary key. |
| `round` | TEXT | NOT NULL | `Puzzle.round` | Clean round code (`T1`, `R2`, `BR`). Part of primary key. |
| `solution` | TEXT | NOT NULL | `Puzzle.solution` | The answer text (the DB holds it; the CLI never prints it). |
| `category` | TEXT | NOT NULL | `Puzzle.category` | |
| `date` | TEXT | NOT NULL | `Puzzle.date` | ISO `YYYY-MM-DD` when parseable, else raw source text (as the parser already produces). |
| `puzzle_number` | INTEGER | NOT NULL | `Puzzle.puzzle_number` | Derived (FR-004). Computing it raises `PuzzleParseError` for an unknown round code → run aborts (FR-010). |
| `puzzle_type` | TEXT | NOT NULL | `Puzzle.puzzle_type` | Derived (FR-004): `Toss-Up` / `Round` / `Bonus Round`. |
| `flags` | TEXT | NOT NULL | `Puzzle.flags` | JSON array of `[column, symbol]` pairs; `"[]"` when none (Decision 4). |

### Primary key & uniqueness

```sql
PRIMARY KEY (season, episode, round)
```

- This is the **stable key** (FR-006); it matches `Puzzle.puzzle_id()`
  (`{season}-{episode}-{round}`).
- Writes use UPSERT on this key (FR-007): an existing row is updated in place; a
  new row is inserted. Re-ingesting the same season produces zero duplicate rows
  (SC-003).
- A within-run collision on this key resolves to a single surviving row (spec
  edge case "duplicate stable key within a single ingest").

### Schema DDL (created on first run, FR-005)

```sql
CREATE TABLE IF NOT EXISTS puzzles (
    season        INTEGER NOT NULL,
    episode       INTEGER NOT NULL,
    round         TEXT    NOT NULL,
    solution      TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    date          TEXT    NOT NULL,
    puzzle_number INTEGER NOT NULL,
    puzzle_type   TEXT    NOT NULL,
    flags         TEXT    NOT NULL DEFAULT '[]',
    PRIMARY KEY (season, episode, round)
);
```

`CREATE TABLE IF NOT EXISTS` makes opening a store idempotent and creates the
database file when absent (FR-005, SC-005).

### Row mapping (Puzzle → row)

For each `Puzzle p` in a parsed season:

| Row column | Value |
|------------|-------|
| `season`, `episode`, `round`, `solution`, `category`, `date` | the corresponding `p.<attr>` |
| `puzzle_number` | `p.puzzle_number` (may raise `PuzzleParseError`) |
| `puzzle_type` | `p.puzzle_type` |
| `flags` | `json.dumps([list(pair) for pair in p.flags])` |

## Validation rules

- All columns are `NOT NULL`; the parser already guarantees non-empty
  `solution`/`round`/`episode` (it skips malformed rows), so a parsed `Puzzle`
  always has the six source values.
- `puzzle_number` must be derivable; if not, the season containing the puzzle is
  rolled back (writes none of its rows) and the run halts (FR-010) — the row is
  never partially inserted.
- Each season is atomic: either all of that season's rows commit, or none do
  (FR-011a). Across a range the run is best-effort — cleanly-parsed seasons commit
  even if another season is skipped for a retrieval failure (FR-011, Decision 5).

## Entity: `IngestSummary` (in-memory result, not stored)

Returned by `ingest_seasons` and rendered by the CLI (spoiler-free, FR-009).

| Field | Type | Meaning |
|-------|------|---------|
| `seasons` | list[int] | The season numbers **committed**, in order. |
| `skipped` | list[int] | Requested seasons skipped due to a retrieval failure (best-effort, FR-011). |
| `unparsed` | list[int] | Requested seasons retrieved but containing no recognizable puzzle table (distinct from a retrieval failure). |
| `added` | int | Rows newly inserted across the committed seasons. |
| `updated` | int | Existing rows updated in place across the committed seasons. |
| `total` | int | `added + updated` (puzzles written). Counts each stable key once, even if a season parsed a duplicate of it. |

No solutions or puzzle text appear in this summary. A non-empty `skipped` or
`unparsed` list corresponds to a non-zero process exit code.

## Value object: season specifier (parsed argument, not stored)

The ingest argument is parsed by `parse_season_arg(text) -> list[int]`:

| Input | Result | Rule |
|-------|--------|------|
| `"40"` | `[40]` | single season |
| `"37-40"` | `[37, 38, 39, 40]` | inclusive ascending range |
| `"40-40"` | `[40]` | equal endpoints ≡ single season (FR-008b) |
| `"40-37"` | error | start > end rejected (FR-008b) |
| `""`, `"abc"`, `"-5"`, `"3-"`, `"a-b"` | error | malformed → rejected with usage message (FR-008) |

The returned list defines exactly which season pages may be fetched (FR-008a); no
other season is retrieved.

## State transitions

None. A puzzle row is written once and thereafter updated in place; there is no
lifecycle/state machine. The database grows monotonically by default (additive
re-ingestion, FR-007a) — rows are never deleted except by an explicit,
out-of-scope prune operation.

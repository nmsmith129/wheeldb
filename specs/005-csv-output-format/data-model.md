# Phase 1 Data Model: CSV Output Format

This feature introduces no new domain entity — it is an alternative serialization
of the existing `Puzzle` record (see `specs/001-episode-puzzle-parser/data-model.md`
and `specs/002-sqlite-database-creation/data-model.md`). What is new is the **CSV
file layout** and the **in-memory working set** the store maintains.

## CSV row schema

One header row plus one data row per puzzle. Columns, in this exact order:

| # | Column | Source | Type on disk | Notes |
|---|--------|--------|--------------|-------|
| 1 | `season` | `Puzzle.season` | integer text | part of identity |
| 2 | `episode` | `Puzzle.episode` | integer text | part of identity |
| 3 | `date` | `Puzzle.date` | ISO `YYYY-MM-DD` string, verbatim | |
| 4 | `puzzle_type` | `Puzzle.puzzle_type` (derived) | text | `Toss-Up` / `Round` / `Bonus Round` |
| 5 | `puzzle_number` | `Puzzle.puzzle_number` (derived) | integer text | `0` for Bonus Round |
| 6 | `category` | `Puzzle.category` | text | CSV-quoted if needed |
| 7 | `solution` | `Puzzle.solution` | text | CSV-quoted if needed |
| 8 | `flags` | `Puzzle.flags` | JSON array text | `json.dumps([list(p) for p in flags])`; empty → `[]` |

`round` is **not** a stored column; columns 4–5 together encode it (see Identity).

## Identity & uniqueness

- **Storage identity (de-dup key)**: `(season, episode, round)` — identical to the
  SQLite primary key. A re-ingested puzzle with the same identity overwrites the
  prior row in place; a new identity appends a row; all other rows are untouched
  (FR-004).
- For a freshly parsed `Puzzle`, the key uses `puzzle.round` directly.
- For a row read back from an existing file, `round` is **reconstructed** from
  columns 4–5 by `round_from_type_and_number(puzzle_type, puzzle_number)`:

  | `puzzle_type` | `puzzle_number` | → `round` |
  |---------------|-----------------|-----------|
  | `Bonus Round` | `0` | `BR` |
  | `Toss-Up` | `N` | `TN` |
  | `Round` | `N` | `RN` |
  | anything else | — | **raises `PuzzleParseError`** (halts the season) |

- **Note (consistency)**: the `Puzzle` dataclass's *value equality* uses
  `(season, episode, round, solution)`, but **storage identity** is only
  `(season, episode, round)`. `solution` is a value of the row, not part of its
  identity. The two must not be conflated.

## In-memory working set (`CsvPuzzleStore`)

- An insertion-ordered `dict` mapping `(season, episode, round)` → ordered field
  values for the row. Populated from the file on open (after header validation);
  mutated by `upsert()`; serialized back to the file on `commit()`.
- Insertion order is the on-disk row order: existing rows keep their order; newly
  added keys are appended (FR-004, Decision 7).

## Validation rules

| Rule | Source | Behavior on violation |
|------|--------|-----------------------|
| Existing file header must exactly equal the 8-column header | FR-012 | raise `DatabaseError`, file untouched |
| Existing row must reconstruct to a valid round code | FR-004 | raise `PuzzleParseError`, season halts |
| A freshly ingested puzzle's round must yield a puzzle number | FR-010 (reused) | raise `PuzzleParseError` before any write |
| `--format` must be one of `sqlite`, `csv` | FR-011 | argparse error, non-zero exit |

## State transitions (per season transaction)

```
open file ──► validate header ──► load rows into dict (reconstruct keys)
   │                                        │
   └─ (file absent/empty: empty dict)       ▼
                                   begin transaction (snapshot dict)
                                            │
                              upsert() × N  │  (added/updated vs dict)
                                            ▼
                         clean exit ──► commit: write temp file ──► os.replace
                         exception  ──► rollback: restore snapshot, file untouched
```

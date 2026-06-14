# Contract: `PuzzleStore` (SQLite persistence)

The single module that knows the SQLite schema and SQL (`storage.py`). It maps
`Puzzle` value objects to rows and back, idempotently. Usable without the CLI and
without network (Principle I); testable against a `tmp_path` database.

## Construction & schema

```python
PuzzleStore(path: str | os.PathLike) -> PuzzleStore
```

- Opens (creating if absent, FR-005) the SQLite database at `path` and ensures
  the `puzzles` table exists via `CREATE TABLE IF NOT EXISTS` (see
  [data-model.md](../data-model.md)).
- Opening an existing, already-populated database is a no-op for data (schema
  creation is idempotent).
- Raises `DatabaseError` (a new `WheelDBError` subclass in `errors.py`) if the
  database cannot be opened or the schema cannot be created.
- Supports use as a context manager (`with PuzzleStore(path) as store: ...`) so
  the connection is closed deterministically.

## Transaction boundary

```python
store.begin()        # start a unit of work
store.commit()       # persist all writes since begin()
store.rollback()     # discard all writes since begin()
```

Or, preferred, a context-managed transaction:

```python
with store.transaction():
    store.upsert(puzzle)        # one or many
# commits on clean exit; rolls back on any exception
```

Each **season** is performed inside its own transaction so that season is
all-or-nothing (FR-011a). A range runs one transaction per season and commits
them independently (best-effort, Decision 5) — the store exposes the transaction
boundary; the `ingest` orchestration decides per-season commit/rollback/skip.

## Writing puzzles

```python
store.upsert(puzzle: Puzzle) -> Literal["added", "updated"]
```

- Computes the row from `puzzle`, including derived `puzzle_number` and
  `puzzle_type` and JSON-serialized `flags` (see data-model row mapping).
- Executes `INSERT ... ON CONFLICT(season, episode, round) DO UPDATE SET ...`.
- Returns `"added"` if no row previously existed for the key, else `"updated"`
  (determined by a `SELECT 1` existence check immediately before the write,
  within the same transaction).
- **Raises `PuzzleParseError`** (propagated from `Puzzle.puzzle_number`) if the
  round code yields no derivable number — the caller lets this abort and roll
  back the transaction (FR-010). The store performs no write for that puzzle.
- Raises `DatabaseError` for an underlying `sqlite3` error.

A convenience may be provided:

```python
store.upsert_many(puzzles: Iterable[Puzzle]) -> tuple[int, int]  # (added, updated)
```

which applies `upsert` to each puzzle within the current transaction and tallies
the results. If any puzzle raises (e.g. `PuzzleParseError`), the exception
propagates and no partial counts are returned (the transaction will be rolled
back by the caller).

## Reading (for verification / summaries)

```python
store.count() -> int                       # total rows in the table
store.count_for_season(season: int) -> int # rows for one season
```

These support tests and the run summary; they never expose data on CLI stdout.

## Idempotency guarantees

- Upserting the same `Puzzle` twice yields exactly one row (SC-003).
- Re-ingesting a season updates changed rows in place and leaves untouched rows
  as-is; previously stored rows absent from the new parse are **not** deleted
  (FR-007a, additive-by-default).

## Errors

| Raised | When |
|--------|------|
| `DatabaseError` | DB cannot be opened, schema creation fails, or a `sqlite3` error occurs during a write/read. |
| `PuzzleParseError` | `Puzzle.puzzle_number` cannot derive a number (unknown round code) while building a row — signals the data-error abort (FR-010). |

`DatabaseError` is added to `errors.py` as `class DatabaseError(WheelDBError)`,
reusing the existing error hierarchy (Principle IV).

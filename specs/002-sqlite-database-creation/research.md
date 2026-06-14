# Phase 0 Research: SQLite Puzzle Database

No `NEEDS CLARIFICATION` markers remained after `/speckit-clarify` (the abort-on-
data-error, additive re-ingestion, and season/range invocation decisions are
already recorded in spec.md). This document records the technical decisions the
design rests on.

## Decision 1: stdlib `sqlite3`, no new dependency

- **Decision**: Use Python's standard-library `sqlite3` module directly; no ORM,
  no third-party driver.
- **Rationale**: The constitution fixes the stack as "Python with SQLite". The
  schema is a single flat table with one composite key; an ORM would add a
  dependency and indirection for no benefit. `sqlite3` ships with CPython 3.11
  and bundles a SQLite new enough (3.24+) for UPSERT (`ON CONFLICT ... DO
  UPDATE`). Keeping dependencies minimal matches the existing `pyproject.toml`.
- **Alternatives considered**: SQLAlchemy / `sqlite-utils` (rejected — extra
  dependency, hides the schema the constitution wants visible and testable);
  hand-rolled file format (rejected — SQLite is mandated and gives us
  transactions and idempotency for free).

## Decision 2: idempotency via composite primary key + UPSERT

- **Decision**: `puzzles` has `PRIMARY KEY (season, episode, round)`. Writes use
  `INSERT INTO puzzles (...) VALUES (...) ON CONFLICT(season, episode, round) DO
  UPDATE SET ...` so an already-stored puzzle is updated in place.
- **Rationale**: This is exactly the stable identity the spec chose and that
  `Puzzle.puzzle_id()` already expresses (`{season}-{episode}-{round}`). UPSERT
  gives FR-007 (update-in-place, no duplicates) in one statement and is naturally
  idempotent, satisfying the constitution's idempotent-runs constraint.
- **Added vs updated counts (FR-009)**: UPSERT alone does not report which rows
  were inserts vs updates. The store will determine this by checking row
  existence for each key immediately before the write within the same
  transaction (a cheap `SELECT 1 ... LIMIT 1`), incrementing an `added` or
  `updated` tally accordingly. Returned to the caller as a small summary object.
- **Alternatives considered**: `INSERT OR REPLACE` (rejected — it DELETEs then
  INSERTs, which would fire ON DELETE side effects and reset any future
  auto-managed columns, and muddies added/updated accounting); pre-`SELECT` then
  branch to INSERT/UPDATE in Python (rejected — two round-trips and a race that
  UPSERT avoids; we still do a lightweight existence check but let one UPSERT
  statement do the write).

### Note on the (season, episode, round) key vs feature 001

Feature 001's data-model noted `solution` as a *tie-breaker* against a rare
duplicated round label, to keep two such rows distinct. This feature's spec
deliberately chose `(season, episode, round)` as the **stable key** and its
"duplicate stable key within a single ingest" edge case explicitly accepts a
single surviving row. We therefore key on `(season, episode, round)` only; if two
parsed rows collide on that key in one run, the later UPSERT wins (one row), which
is the spec's intended behavior. This is recorded here so the divergence from the
001 tie-breaker note is intentional and traceable.

## Decision 3: derived columns stored, computed at write time

- **Decision**: `puzzle_number` (INTEGER) and `puzzle_type` (TEXT) are stored
  columns, computed by reading `Puzzle.puzzle_number` / `Puzzle.puzzle_type`
  when building the row.
- **Rationale**: The user explicitly requires both to be stored per row.
  Computing them from the existing model derivations (Principle IV) keeps a
  single source of truth. Storing them denormalized makes the database directly
  queryable (e.g. "all bonus-round puzzles") without recomputation.
- **Abort trigger (FR-010)**: `Puzzle.puzzle_number` raises `PuzzleParseError`
  for an unrecognized round code; `puzzle_type` returns `"Unknown"` and never
  raises. So the data-error abort is driven by `puzzle_number` raising while the
  row is being built. The ingest layer lets that propagate to roll back the
  transaction and reports the offending round code. (`puzzle_type` == "Unknown"
  alone is not treated as an abort — a recognized round always yields a number.)

## Decision 4: `flags` serialized as JSON text

- **Decision**: Store `Puzzle.flags` (a tuple of `(column, symbol)` pairs) as a
  JSON string in a `flags` TEXT column; `()` serializes to `"[]"`.
- **Rationale**: Keeps "one puzzle = one row" (no child table) while preserving
  all attributes. JSON via the stdlib `json` module is queryable enough for the
  rare annotation case and round-trips losslessly. A child table would violate
  the one-row rule for no current query need.
- **Alternatives considered**: separate `puzzle_flags` table (rejected — breaks
  one-row rule, premature); dropping flags (rejected — spec says store *all*
  attributes).

## Decision 5: per-season atomic writes, best-effort across a range

- **Decision**: Each season is its own unit of work — fetched, parsed, and
  written inside its own `PuzzleStore` transaction, committed before the next
  season begins. The run processes the resolved seasons in ascending order:
  - A season that retrieves and parses cleanly is **committed** (atomically — all
    its rows or none, FR-011a).
  - A `RetrievalError` for a season is **reported and skipped**; the run continues
    with the remaining seasons (best-effort, FR-011). The process exits non-zero
    if any season was skipped.
  - A `PuzzleParseError` (data error: a round code with no derivable number)
    **rolls back that season** (writes none of its rows) and **halts** the run —
    no further seasons are processed — and is reported with the offending round
    code (FR-010). Seasons committed earlier in the range are retained. The
    process exits non-zero.
  - A `sqlite3`/`DatabaseError` likewise rolls back the current season and halts.
- **Rationale**: Matches the user's best-effort decision (2026-06-14): a large
  backfill should not lose every good season because one page is unavailable.
  Per-season atomicity keeps the strong half of FR-011 — no individual season is
  ever half-written — while allowing the range to make partial progress. Data
  errors remain a hard stop because they signal unexpected markup the operator
  must investigate, not a merely missing page.
- **Absent vs blocked season**: the existing `fetch` layer raises `RetrievalError`
  for *any* non-retrievable page and cannot distinguish "season page does not
  exist" from "blocked/network error". Both are therefore treated as a skip. If a
  future change needs to halt on a genuine network block while skipping only
  truly-absent seasons, the `fetch` layer must first surface that distinction
  (e.g. HTTP 404 vs 403); deferred.
- **Summary reporting**: `IngestSummary` records the seasons **committed** and the
  seasons **skipped** so the CLI can report both (FR-009).

## Decision 6: default database path, overridable

- **Decision**: Default to a single file `wheeldb.sqlite` in the current working
  directory; the CLI accepts `--db PATH` to override, and `ingest_seasons` /
  `PuzzleStore` accept an explicit path so tests use `tmp_path`.
- **Rationale**: A sensible zero-config default (FR-005: created automatically on
  first run) with an escape hatch for tests and alternate locations. Tests never
  touch a shared/persistent file.
- **Alternatives considered**: in-memory default (rejected — the product is a
  durable database); XDG/AppData location (rejected — over-engineered for a
  single-maintainer scraping tool; a workspace-local file is clearer).

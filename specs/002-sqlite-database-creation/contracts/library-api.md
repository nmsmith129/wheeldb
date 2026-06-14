# Contract: Public Library API (additions)

New Python surface added by this feature, exported from `wheeldb`. Existing
exports (`Puzzle`, `extract_episode`, `Fetcher`, `HttpFetcher`, `season_url`,
`WheelDBError`, `RetrievalError`, `ParseError`) are unchanged.

## `parse_season_arg`

```python
parse_season_arg(text: str) -> list[int]
```

Parse the ingest argument into the explicit, ascending list of season numbers to
process.

- `"40"` → `[40]`; `"37-40"` → `[37, 38, 39, 40]`; `"40-40"` → `[40]`.
- Raises `ValueError` for a malformed argument or a reversed range (`"40-37"`,
  `""`, `"abc"`, `"-5"`, `"3-"`, `"a-b"`). The CLI converts this into a usage
  error (FR-008/FR-008b).
- The returned list is the **complete** set of seasons that may be fetched
  (FR-008a) — callers MUST NOT fetch any season outside it.

## `ingest_seasons`

```python
ingest_seasons(
    season_arg: str | Iterable[int],
    *,
    db_path: str | os.PathLike,
    fetcher: Fetcher | None = None,
) -> IngestSummary
```

Ingest every puzzle of the requested season(s) into the SQLite database at
`db_path`, reusing the existing parser.

- `season_arg`: a raw arg string (`"40"`, `"37-40"`) parsed via
  `parse_season_arg`, **or** an already-resolved iterable of season ints.
- `fetcher`: a `Fetcher` (defaults to a live `HttpFetcher`); tests inject a
  `FixtureFetcher`. Only the resolved seasons are fetched (FR-008a).
- For each season (ascending): `fetcher.get_season_html(season)` →
  `parser.find_puzzle_table` → `parser.parse_rows(table, season)` →
  `store.upsert_many(...)`, each inside that season's own `store.transaction()`.
  No new parsing path is introduced (FR-001).
- **Best-effort per season** (Decision 5):
  - A season that retrieves and parses cleanly is committed; its `added`/`updated`
    tallies and its season number (in `seasons`) accrue to the summary.
  - A `RetrievalError` for a season rolls back that season, records it in
    `skipped`, and the loop **continues** with the next season (FR-011).
  - A `ParseError` (page retrieved but no recognizable puzzle table) records the
    season in `unparsed` and the loop **continues** (distinct from a retrieval
    failure so the CLI can report it accurately).
  - A within-run duplicate stable key collapses to one row (last write wins) and
    is counted once in `added`/`updated`/`total`.
  - A `PuzzleParseError` (data error) or `DatabaseError` rolls back that season
    and **re-raises** — the caller (CLI) reports it and exits non-zero; seasons
    committed earlier remain (FR-010).
- Returns an `IngestSummary` when the run completes (including when some seasons
  were skipped). Raises only on a data error / DB error (the halting cases).
- Never prints anything (the CLI owns spoiler-free rendering).

### `IngestSummary`

A small immutable result (e.g. a dataclass):

| Field | Type | Meaning |
|-------|------|---------|
| `seasons` | `list[int]` | seasons committed, in order |
| `skipped` | `list[int]` | seasons skipped on a retrieval failure (best-effort) |
| `unparsed` | `list[int]` | seasons retrieved but with no recognizable puzzle table |
| `added` | `int` | rows newly inserted |
| `updated` | `int` | rows updated in place |
| `total` | `int` | `added + updated` (each stable key counted once) |

Contains no puzzle text (FR-009). A non-empty `skipped` or `unparsed` list maps
to a non-zero CLI exit.

## `PuzzleStore`

The persistence class — see [storage-contract.md](storage-contract.md) for the
full contract. Exported so library consumers (and tests) can open and query a
database directly.

## `DatabaseError`

```python
class DatabaseError(WheelDBError): ...
```

Raised for SQLite-level failures (open/schema/write). Added to `errors.py`,
extending the existing `WheelDBError` base (Principle IV).

## Updated package exports (`wheeldb/__init__.py`)

Adds: `ingest_seasons`, `parse_season_arg`, `PuzzleStore`, `IngestSummary`,
`DatabaseError` to `__all__`.

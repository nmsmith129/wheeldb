# Store Contract: `CsvPuzzleStore`

`CsvPuzzleStore` is a drop-in alternative to `PuzzleStore` (see
`specs/002-sqlite-database-creation/contracts/storage-contract.md`). It exposes the
**same method names and semantics** so `ingest_seasons` drives either store
unchanged (Principle IV). Differences from `PuzzleStore` are noted inline.

## Interface (mirrors `PuzzleStore`)

| Member | Contract |
|--------|----------|
| `__init__(path)` | Record the CSV path. If the file exists and is non-empty, validate its header equals the canonical 8-column header exactly; on mismatch raise `DatabaseError` (file untouched). Load existing rows into an insertion-ordered dict keyed `(season, episode, round)`, reconstructing `round` from the `puzzle_type`/`puzzle_number` columns (raises `PuzzleParseError` on an unrecognized pair). An absent or empty file → empty dict. |
| `__enter__ / __exit__` | Context manager; `__exit__` closes (no resource beyond the in-memory dict) and does not suppress exceptions. |
| `transaction()` | Contextmanager that snapshots the dict on entry; on clean exit calls `commit()`, on any exception calls `rollback()` and re-raises. Same shape as `PuzzleStore.transaction`. |
| `upsert(puzzle) -> str` | Read `puzzle.puzzle_number` first (may raise `PuzzleParseError` before any mutation, FR-010). Key = `(season, episode, puzzle.round)`. Return `"updated"` if the key is already in the dict, else `"added"`; set the dict entry to the serialized row (last-wins). |
| `commit()` | Atomically rewrite the **entire** file from the dict: write a sibling temp file (header + rows in insertion order), then `os.replace()` into the target path. |
| `rollback()` | Restore the dict from the entry snapshot; the on-disk file is not touched. |
| `count() -> int` | Number of rows in the dict. |
| `count_for_season(season) -> int` | Number of dict keys whose season matches. |

## Canonical header (exact)

```
season,episode,date,puzzle_type,puzzle_number,category,solution,flags
```

## Serialization

- `csv` module, `excel` dialect, files opened `newline=""`, `lineterminator="\n"`,
  UTF-8. Embedded commas/quotes/newlines round-trip via standard quoting (FR-007).
- `flags` cell = `json.dumps([list(pair) for pair in puzzle.flags])` (empty → `[]`),
  carried through verbatim on read (never re-parsed by the store).
- `date` written verbatim as the model's ISO string; integers written as text.

## Guarantees (parity with `PuzzleStore`)

- **Idempotent**: re-ingesting a season yields the same row count; matching keys
  overwrite in place (FR-004).
- **added/updated**: returned per `upsert`, relative to the file's prior contents;
  `ingest`'s existing `seen_keys` logic collapses within-run duplicate keys and
  counts each once (FR-005).
- **All-or-nothing per season**: a season either fully lands (atomic
  `os.replace`) or the file is unchanged, including on mid-write interruption
  (FR-009).
- **No spoilers**: the store writes the product file but prints nothing
  (Principle II).

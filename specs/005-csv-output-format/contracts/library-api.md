# Library API Contract: new/changed public surface

## New

### `wheeldb.csv_storage.CsvPuzzleStore`

A CSV-backed puzzle store mirroring `wheeldb.storage.PuzzleStore`. See
[csv-store-contract.md](csv-store-contract.md) for the full method contract.
Exported from `wheeldb.__init__`.

### `wheeldb.models.round_from_type_and_number(puzzle_type, puzzle_number) -> str`

Pure inverse of the `Puzzle.puzzle_type` / `Puzzle.puzzle_number` derivations.

- **Parameters**: `puzzle_type` (`"Toss-Up"` / `"Round"` / `"Bonus Round"`),
  `puzzle_number` (int).
- **Returns**: the round code — `"BR"`, `"T<N>"`, or `"R<N>"`.
- **Raises**: `PuzzleParseError` if the pair does not map to a recognized code.
- **Co-located** with its forward counterparts in `models.py` to keep the
  round↔type/number mapping a single source of truth (Principle IV).

## Changed

### `wheeldb.ingest.ingest_seasons(...)`

Gains the ability to target either store. The season loop, best-effort handling,
`seen_keys` de-duplication, and `IngestSummary` are **unchanged** — only the store
construction is selected by format (e.g. a `store_format="sqlite"` parameter, or an
injected store factory; chosen in tasks). Existing callers that pass `db_path`
without a format keep today's SQLite behavior (FR-002).

### `wheeldb.cli`

The `ingest` subparser gains `--format {sqlite,csv}` (default `sqlite`) and derives
the `.csv` output path from `--db` when CSV is selected. See [cli.md](cli.md).

## Unchanged / reused (no duplication — Principle IV)

`PuzzleStore`, `Puzzle` + its derivations, `parser`, `fetch`, and the
`errors.WheelDBError` hierarchy (`DatabaseError`, `PuzzleParseError`) are reused
as-is.

# Library API Contract: new/changed public surface

## New

### `wheeldb.gamegen`

- `generate_game(season, *, store, games_dir="games", seed=None, template_path=...) -> str`
  — select 4 Round / 3 Toss-Up / 1 Bonus Round puzzles from `season` (seeded if
  `seed` given), assign them to the eight slots, write the next `wof[N].pptm`, and
  return the created file path. Raises `GameError` on the validation failures in
  data-model.md. Prints nothing (the CLI owns spoiler-free output).
- `next_game_number(games_dir) -> int` — smallest unused `1..999` (FR-003/FR-011).

### `wheeldb.pptx_inject`

- `inject_puzzles(template_path, out_path, slot_assignments)` and `SLOT_MAPPING` —
  see [injector-contract.md](injector-contract.md).

### `wheeldb.errors.GameError(WheelDBError)`

Raised for generation failures (season absent, insufficient puzzles, no number
available, template/package problems) so the CLI maps them to a clear error + exit 2.

## Changed

### `wheeldb.storage.PuzzleStore`

- `puzzles_for_season(season) -> list[Puzzle]` — return the season's puzzles as
  `Puzzle` objects, for `gamegen` to group by type. Reuses the existing row→Puzzle
  mapping; no new data path (Principle IV). (A parity method on
  `csv_storage.CsvPuzzleStore` is deferred until feature 005 merges.)

### `wheeldb.cli`

- New `game` subcommand (see [cli.md](cli.md)).

## Unchanged / reused

`models.Puzzle` + derivations, the store's open/transaction lifecycle, the
`errors.WheelDBError` hierarchy, and the `season_url`/ingest conventions are reused
as-is.

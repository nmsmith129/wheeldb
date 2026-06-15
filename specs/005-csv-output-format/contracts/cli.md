# CLI Contract: `ingest --format {sqlite,csv}`

Extends the existing `ingest` subcommand (see
`specs/002-sqlite-database-creation/contracts/cli.md`). No other command changes.

## Synopsis

```
wheeldb ingest <season|range> [--db PATH] [--format {sqlite,csv}] [--from-dir DIR]
```

## Options

| Option | Default | Meaning |
|--------|---------|---------|
| `--format` | `sqlite` | Output format. `sqlite` is unchanged behavior (FR-002). `csv` writes a CSV file instead. An unsupported value is rejected by argparse with a usage error and non-zero exit (FR-011). |
| `--db PATH` | `wheeldb.sqlite` | The output path. Under `--format csv` the effective file is `Path(PATH).with_suffix(".csv")` (FR-002a): `wheeldb.sqlite → wheeldb.csv`; `wheeldb → wheeldb.csv`; `my.data.sqlite → my.data.csv`. |

## Behavior

- `--format sqlite` (or omitted): identical to today — writes the SQLite database.
- `--format csv`: ingest writes puzzles to the derived `.csv` path using
  `CsvPuzzleStore`. Counts, season/skip/unparsed reporting, provenance lines, and
  exit codes are **identical** to the SQLite path for the same input (FR-005).

## Output (stdout, spoiler-free — Principle II / FR-010)

Same summary format as the SQLite path; only the target path in the header line
differs (it names the `.csv` file). No puzzle solution is ever printed.

```
Ingested season 42 into wheeldb.csv
  Puzzles: 3 added, 0 updated (3 total)
  Source: <season 42 url>
```

## Exit codes (unchanged mapping)

| Code | Condition |
|------|-----------|
| 0 | Clean run (including zero puzzles found) |
| 2 | Bad season argument; a skipped or unparsed season; a halting `PuzzleParseError` or `DatabaseError` (e.g. header mismatch, FR-012) |

## Errors (stderr)

- Header mismatch on a pre-existing CSV → `error: database error: ...` (from
  `DatabaseError`), file left untouched, exit 2.
- Unrecognized round on a pre-existing row → `error: cannot derive puzzle number:
  ...` (from `PuzzleParseError`), exit 2.
- Invalid `--format` value → argparse usage error, exit 2.

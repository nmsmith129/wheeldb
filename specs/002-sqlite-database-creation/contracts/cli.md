# Contract: CLI `ingest` subcommand (spoiler-free)

Per Principle II: arguments in, results to stdout, errors/diagnostics to stderr,
and **no puzzle solutions printed during normal operation**. The database file
holds solutions (it is the product); the CLI never prints them.

## Invocation

```text
wheeldb ingest <SEASON|RANGE> [--db PATH]
```

(Equivalently `python -m wheeldb ingest <SEASON|RANGE> [--db PATH]`.)

| Argument | Required | Meaning |
|----------|----------|---------|
| `<SEASON\|RANGE>` | yes | A single season (`40`) or an inclusive range (`37-40`). No other form is accepted (FR-008). |
| `--db PATH` | no | SQLite file to write (default: `wheeldb.sqlite` in the CWD). Created if absent (FR-005). |

The existing `wheeldb episode <N>` command is unchanged.

## Argument grammar (FR-008, FR-008b)

| Input | Seasons processed |
|-------|-------------------|
| `40` | `[40]` |
| `37-40` | `[37, 38, 39, 40]` (inclusive, ascending) |
| `40-40` | `[40]` |
| `40-37` | **rejected** (start > end) |
| empty / `abc` / `-5` / `3-` / `a-b` | **rejected** (malformed) |

A rejected argument prints a usage message to stderr, writes nothing, and exits
non-zero (SC-007).

## stdout (success)

A spoiler-free summary — counts, seasons, and provenance only:

```text
Ingested seasons 37-40 into wheeldb.sqlite
  Puzzles: 812 added, 0 updated (812 total)
  Sources:
    https://buyavowel.boards.net/page/compendium37
    https://buyavowel.boards.net/page/compendium38
    https://buyavowel.boards.net/page/compendium39
    https://buyavowel.boards.net/page/compendium40
```

Single-season form:

```text
Ingested season 40 into wheeldb.sqlite
  Puzzles: 203 added, 0 updated (203 total)
  Source: https://buyavowel.boards.net/page/compendium40
```

Re-running the same request reports the same totals as `updated` (idempotent,
SC-003):

```text
  Puzzles: 0 added, 203 updated (203 total)
```

- Reports puzzles **added**, **updated**, and **total**, the **season(s)
  committed**, any **season(s) skipped**, and the **source URL(s)** (provenance,
  via `season_url`).
- MUST NOT print any `solution`, or any puzzle text that reveals an answer
  (FR-009, SC-004).

### Best-effort range with a skipped season

When a season in a range cannot be retrieved, the others still commit and the
skipped season is reported (FR-011); the process exits non-zero:

```text
Ingested seasons 37, 39-40 into wheeldb.sqlite (season 38 skipped)
  Puzzles: 606 added, 0 updated (606 total)
  Skipped: season 38 (could not retrieve source)
  Sources:
    https://buyavowel.boards.net/page/compendium37
    https://buyavowel.boards.net/page/compendium39
    https://buyavowel.boards.net/page/compendium40
```

## stderr + exit codes

| Condition | stderr | Exit code | DB effect |
|-----------|--------|-----------|-----------|
| Success (all requested seasons committed) | progress/diagnostics only (e.g. "ingesting season 38…") | `0` | all committed |
| Malformed/invalid argument (incl. reversed range) | usage message | non-zero (e.g. `2`) | unchanged (nothing fetched) |
| Retrieval failure of one or more seasons (best-effort) | a `Skipped: season(s) <S> (could not retrieve source)` line | non-zero (e.g. `2`) | cleanly-parsed seasons committed; skipped seasons contribute nothing |
| Season retrieved but no puzzle table | a `No puzzle table: season(s) <S> (retrieved, but no puzzles found)` line | non-zero (e.g. `2`) | cleanly-parsed seasons committed; the table-less season contributes nothing |
| Data error (round code yields no puzzle number) | `error: cannot derive puzzle number for round <code> (season S, episode E)` | non-zero (e.g. `2`) | the offending season rolled back, run halts; seasons committed earlier retained |

Each season is written atomically — no individual season is ever left
half-written (FR-011a). A malformed argument and a single-season run that fails
both leave the database entirely unchanged.

## Notes

- Progress/diagnostic lines go to **stderr**, so stdout stays a clean,
  machine-readable summary.
- Only the requested season(s) are fetched; no other season page is retrieved
  (FR-008a, SC-008).
- The full puzzle rows (with solutions) live only in the database file and the
  library/test boundary — never on CLI stdout.

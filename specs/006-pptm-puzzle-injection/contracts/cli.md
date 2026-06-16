# CLI Contract: `wheeldb game`

A new subcommand on the existing `wheeldb` CLI. Spoiler-free (Constitution II).

## Synopsis

```
wheeldb game <season> [--seed N] [--db PATH] [--games-dir DIR]
```

## Arguments / options

| Arg/Option | Default | Meaning |
|------------|---------|---------|
| `season` (positional) | — | The season to draw puzzles from (must exist in the store). |
| `--seed N` | none (system entropy) | Optional integer seed; makes selection deterministic/reproducible (FR-012). |
| `--db PATH` | `wheeldb.sqlite` | The ingested SQLite store to read (same convention as `ingest`). |
| `--games-dir DIR` | `games` | Output directory; created if absent. |

> **Scope note**: this feature reads the **SQLite** store only. A `--format csv`
> option (reading the CSV store from feature 005) is deferred until feature 005 is
> merged; it is intentionally out of scope here to avoid advertising an inert
> option.

## Behavior

- Selects 4 Round + 3 Toss-Up + 1 Bonus Round puzzles at random (seeded if `--seed`)
  from the season, fills the template's eight slots, and writes
  `<games-dir>/wof[N].pptm` at the smallest unused three-digit `N`, never
  overwriting (FR-003). The template and its VBA are not modified (FR-004).

## Output (stdout, spoiler-free — FR-009/SC-005)

Reports only the created file and the slot counts; never a solution or category:

```
Created games/wof001.pptm from season 41
  Puzzles: 4 Round, 3 Toss-Up, 1 Bonus Round (8 total)
```

## Exit codes

| Code | Condition |
|------|-----------|
| 0 | A game file was created. |
| 2 | Bad argument; season absent; insufficient puzzles of a type; no number available; template missing/unreadable (a `GameError`). |

## Errors (stderr, spoiler-free — Decision 7)

- Season absent: `error: season 99 not found in <store>`.
- Insufficient type: `error: season 41 has 2 Toss-Up puzzles; need 3` (counts only).
- All numbers used: `error: no available wof[N].pptm name in <games-dir> (001-999 used)`.
- Template missing: `error: template WheelofFortune6.4.pptm not found`.
- Slot unlocatable: `error: puzzle slot <n> anchor not found in template` (FR-013).

Each message above is distinguishable by condition (FR-014) and validation runs in
a fixed order — template, then season presence, then per-type counts, then number
availability (FR-015) — stopping at the first failure with no file written (FR-016).
A `--seed` only affects which puzzles are chosen once selection is reached; it never
changes this order. Concurrent invocations racing for the same number are out of
scope (Edge Cases).

# wheeldb

Extract every puzzle from a Wheel of Fortune episode (by episode number) from the
[Buy A Vowel Boards puzzle compendium](https://buyavowel.boards.net/page/compendiumindex).

The compendium organizes puzzles into one table per season page (no per-episode
page), so `wheeldb` searches season pages, matches the `EP#` column, and returns
the episode's puzzles. See [the format notes](FORMAT.md) and the feature spec in
[specs/001-episode-puzzle-parser/](specs/001-episode-puzzle-parser/).

## Install

```bash
pip install -e .            # or: pip install requests beautifulsoup4
```

## Library use

```python
from wheeldb import extract_episode

puzzles = extract_episode(8011)          # list[Puzzle]
for p in puzzles:
    print(p.round, p.category, p.date)   # your code may show solutions; the library never does on its own
```

Each `Puzzle` exposes six attributes — `solution`, `category`, `date`
(ISO `YYYY-MM-DD`, or raw text when unparseable), `season`, `episode`, `round`
(clean code such as `T1`/`R2`/`BR`) — plus derived `round_name`, `puzzle_type`,
and preserved annotation `flags`.

- A non-existent episode returns an empty list (not an error).
- A retrieval failure (e.g. HTTP 403) raises `RetrievalError`, kept distinct from
  "not found".
- For offline/testing, inject a `Fetcher`: `extract_episode(n, fetcher=my_fetcher)`.

## Command line (spoiler-free)

The CLI reports counts and provenance only — it never prints solutions:

```bash
wheeldb episode 8011
# Episode 8011 (Season 42): 3 puzzles found
#   Rounds: T1, R2, BR
#   Source: https://buyavowel.boards.net/page/compendium42
```

(Equivalently `python -m wheeldb episode 8011`.)

## Building the puzzle database

`wheeldb ingest` stores a season's puzzles in a local SQLite database — one row
per puzzle, carrying all six attributes plus the derived `puzzle_number` and
`puzzle_type`. Invoke it with a single season or an inclusive range:

```bash
wheeldb ingest 40            # one season
wheeldb ingest 37-40         # an inclusive range
wheeldb ingest 40 --db my.sqlite   # custom database path
wheeldb ingest 40 --format csv     # write a CSV file instead of SQLite
```

The database defaults to `wheeldb.sqlite` in the current directory and is created
on first run. Output reports counts, the season(s) committed, and source URLs —
never solutions:

```text
Ingested season 40 into wheeldb.sqlite
  Puzzles: 203 added, 0 updated (203 total)
  Source: https://buyavowel.boards.net/page/compendium40
```

Behavior:

- **Idempotent** — re-ingesting updates rows in place; it never duplicates, and
  it never deletes rows absent from a later parse (additive by default).
- **Best-effort ranges** — a season that can't be retrieved is reported and
  skipped while the others still commit; the command then exits non-zero. Each
  season is written all-or-nothing.
- **Data errors halt** — an unrecognized round code stops the run (that season is
  rolled back) so you can investigate, leaving earlier seasons committed.
- **CSV output** — `--format csv` writes a CSV file instead of SQLite, with the
  same idempotency, counts, and best-effort behavior. The output path is the
  `--db` path with its extension swapped to `.csv` (so the default becomes
  `wheeldb.csv`). Columns, in order: `season, episode, date, puzzle_type,
  puzzle_number, category, solution, flags`. Re-ingesting merges in place keyed on
  `(season, episode, round)`; a pre-existing file whose header does not match
  halts the run, leaving the file untouched.

The output file holds solutions (that is its purpose); the CLI stays
spoiler-free. The default `*.sqlite` files are gitignored.

## Generating a playable game

`wheeldb game` builds a ready-to-play PowerPoint game from the
`WheelofFortune6.4.pptm` template. It selects eight puzzles from an ingested
season — **four Round, three Toss-Up, one Bonus Round**, chosen at random per type —
fills the template's eight puzzle slots, and writes the result to `games/`:

```bash
wheeldb game 42                       # next games/wof[N].pptm from season 42
wheeldb game 42 --seed 7              # reproducible selection (same seed -> same lineup)
wheeldb game 42 --db my.sqlite        # read a specific store (default: wheeldb.sqlite)
wheeldb game 42 --games-dir out       # write into a different directory (created if absent)
```

Output is **`games/wof[N].pptm`**, where `N` is the smallest unused three-digit
number in `001`–`999` (an empty `games/` yields `wof001.pptm`; a deleted middle
number is reused before later ones). Existing files are never overwritten. The
command reports only the created file and the slot counts — never a solution or
category:

```text
Created games/wof001.pptm from season 42
  Puzzles: 4 Round, 3 Toss-Up, 1 Bonus Round (8 total)
```

Behavior:

- **Template & macros preserved** — only the slide parts carrying puzzle text are
  rewritten; `ppt/vbaProject.bin` and every other part are copied through
  byte-for-byte, so the game's macros still run and the original template is left
  unchanged. (The host must enable macros to play the generated file.)
- **Spoiler-free** — neither the success summary nor any error message reveals a
  solution or category. The generated file necessarily contains solutions (it is the
  product); the operator output does not.
- **All-or-nothing errors (exit 2)** — validation runs template present → season
  present → per-type counts → number available, stopping at the first failure with
  **no file written**. A season short on a type reports only the type and counts
  (e.g. `season 42 has 2 Toss-Up puzzles; need 3`).

Generated games live under `games/`, which is gitignored.

## Testing

The suite runs fully offline against saved HTML fixtures:

```bash
pytest                       # all tests, no network
pytest --print-puzzles       # also print parsed puzzles (incl. solutions) to the log
```

Puzzle solutions surface only behind the test boundary (via `--print-puzzles`),
never during normal operation.

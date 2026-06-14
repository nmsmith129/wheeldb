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

## Testing

The suite runs fully offline against saved HTML fixtures:

```bash
pytest                       # all tests, no network
pytest --print-puzzles       # also print parsed puzzles (incl. solutions) to the log
```

Puzzle solutions surface only behind the test boundary (via `--print-puzzles`),
never during normal operation.

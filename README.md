# wheeldb

Scrape Wheel of Fortune puzzles from the [Buy A Vowel Boards Puzzle
Compendium](https://buyavowel.boards.net/page/compendiumindex) into a local
SQLite database, sortable by **season, episode, puzzle type, category, air date,
and round name**.

A single script, `wheeldb.py`, fetches the compendium index, follows each season
link, parses every episode's puzzles, and stores them in SQLite. Re-running it is
safe and idempotent — it *maintains* an existing database rather than duplicating
rows — so the same command both builds the database and keeps it up to date.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Full build (all seasons discovered from the index)
python wheeldb.py --seasons all

# A single season, into a specific database file
python wheeldb.py --db puzzles.db --seasons 42

# A contiguous range of seasons
python wheeldb.py --seasons 30-42

# Cheap maintenance run: refresh only the latest season
python wheeldb.py --update

# Save fetched pages to disk for inspection / building test fixtures
python wheeldb.py --seasons 42 --dump-html --cache-dir html_cache -v
```

### Options

| Flag | Description |
| ---- | ----------- |
| `--db PATH` | SQLite database path (default `puzzles.db`). |
| `--seasons all\|N\|N-M` | Which seasons to scrape (default `all`). |
| `--update` | Scrape only the latest season (maintenance run). |
| `--delay SECONDS` | Politeness delay before each request (default `1.0`). |
| `--cache-dir DIR` | Directory for the on-disk HTML cache (omit to disable). |
| `--dump-html` | Save fetched pages to the cache dir (bypasses cache reads). |
| `-v`, `--verbose` | Verbose logging. |

## Network access note

`buyavowel.boards.net` returns **HTTP 403 to non-browser user agents**, so the
scraper sends a real browser `User-Agent` on every request.

If you run this inside **Claude Code on the web**, the cloud environment's network
egress is restricted by default. Add `buyavowel.boards.net` to the environment's
**Custom** allowed-domains list (keep "include default package managers" checked
so `pip` still works), then start a fresh session. If the host is still blocked,
the script exits with code `2` and a message pointing you here.

## Database schema

A single `puzzles` table, indexed on every sort dimension:

| Column | Notes |
| ------ | ----- |
| `season` | Integer season number. |
| `episode` | Episode number/identifier as shown. |
| `air_date` | ISO `YYYY-MM-DD` when parseable, else the original text. |
| `round_name` | Specific round, e.g. `Toss-Up 1`, `Round 2`, `Bonus Round`. |
| `puzzle_type` | General type derived from the round, e.g. `Toss-Up`, `Round`. |
| `category` | Puzzle category, e.g. `Phrase`, `Before & After`. |
| `solution` | The puzzle text. |
| `source_url`, `scraped_at` | Provenance: page scraped and when. |

Rows are unique on `(season, episode, round_name, solution)`; re-scraping updates
existing rows in place.

### Example queries

```bash
sqlite3 puzzles.db \
  "SELECT season, episode, air_date, round_name, puzzle_type, category, solution
   FROM puzzles ORDER BY season, episode, round_name LIMIT 20;"

sqlite3 puzzles.db "SELECT DISTINCT puzzle_type FROM puzzles;"
sqlite3 puzzles.db "SELECT category, COUNT(*) FROM puzzles GROUP BY category ORDER BY 2 DESC;"
```

## Tests

The suite runs fully offline (saved fixture HTML + mocked HTTP), so it passes even
when the live site is unreachable:

```bash
pip install -r requirements-dev.txt
pytest -q
```

Coverage: index/season parsing, `puzzle_type` derivation, date normalisation,
the SQLite layer (schema, upsert idempotency, sorting by every dimension), the
HTTP layer (browser UA, 403→clear error, retry/backoff, caching), and a full
end-to-end CLI build.

## Note on the parser fixtures

`tests/fixtures/index.html` and `tests/fixtures/season42.html` are representative
stand-ins modelling the compendium's structure. Once the live site is reachable,
capture real pages with `--dump-html`, replace the fixtures, and adjust the
`parse_index` / `parse_season` selectors in `wheeldb.py` if the real markup
differs, then re-run `pytest`.

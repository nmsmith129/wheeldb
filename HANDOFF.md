# HANDOFF — finalize the scraper against the live site

This file is written for a **fresh session with no memory of the original chat**.
Everything you need is here and in the repo.

## Background

`wheeldb.py` is a working single-script scraper for the Buy A Vowel Boards Wheel
of Fortune Puzzle Compendium → SQLite. The full pipeline (fetch → parse → upsert),
the SQLite schema, the CLI, and the offline test suite are **done and passing**.

The one thing that could **not** be finished in the original session: the live
site `buyavowel.boards.net` was unreachable (network egress was not yet open), so
the HTML parser (`parse_index` / `parse_season`) was written against
**representative stand-in fixtures**, not the real markup. Your job is to confirm
or correct the parser against real pages.

## Preconditions

- You are on branch `claude/wof-puzzle-scraper-sqlite-41ewvc`.
- Network egress to `buyavowel.boards.net` is now allowed. Verify:
  ```bash
  curl -sS -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
  (KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
  -o /dev/null -w "%{http_code}\n" https://buyavowel.boards.net/page/compendiumindex
  ```
  Expect `200`. If you get `403` with "Host not in allowlist", egress is still
  blocked — stop and tell the user to add `buyavowel.boards.net` to the
  environment's **Custom** allowed domains and start another fresh session.
- Install deps: `pip install -r requirements-dev.txt`.

## Steps

1. **Capture real pages** to disk:
   ```bash
   python wheeldb.py --seasons 42 --dump-html --cache-dir html_cache -v
   ```
   This writes the index page and the Season 42 page into `html_cache/`.
   (`html_cache/` is gitignored; that's fine — you'll copy trimmed pages into
   `tests/fixtures/` below.)

2. **Inspect the real markup.** Compare the saved index/season HTML against the
   assumptions in `wheeldb.py`:
   - `parse_index` expects season links whose text matches `Season N`.
   - `parse_season` expects `<tr>` rows: episode-header rows matched by
     `_EPISODE_PATTERN` (keyword + numeric episode id + optional air date), and
     puzzle rows matched by `_ROUND_PATTERN` with columns `[round, category,
     solution]`.
   Adjust the selectors / regexes if the real structure differs (e.g. divs
   instead of tables, different column order, separate date column).

3. **Replace the fixtures** with real, lightly-trimmed pages so the tests assert
   against genuine markup:
   - `tests/fixtures/index.html` ← a few real season links from the index.
   - `tests/fixtures/season42.html` ← one real season page (trim to a couple of
     episodes to keep it small).
   Then update the expected values in `tests/test_parser.py` and `tests/test_cli.py`
   (season list, puzzle counts, the exact first-row fields) to match.

4. **Re-run the suite** until green:
   ```bash
   pytest -q
   ```

5. **Live smoke test** one season and inspect the data:
   ```bash
   python wheeldb.py --db /tmp/test.db --seasons 42 -v
   sqlite3 /tmp/test.db \
     "SELECT season, episode, air_date, round_name, puzzle_type, category, solution
      FROM puzzles ORDER BY season, episode, round_name LIMIT 20;"
   sqlite3 /tmp/test.db "SELECT DISTINCT puzzle_type FROM puzzles;"
   ```
   Confirm fields look right and `puzzle_type` is the round name minus its
   instance marker (e.g. "Toss-Up 1" → "Toss-Up").

6. **Confirm idempotency:** run the same `--seasons 42` command again and verify
   the row count is unchanged (upsert, no duplicates).

7. **Full build:**
   ```bash
   python wheeldb.py --seasons all -v
   ```

8. **Commit and push** to `claude/wof-puzzle-scraper-sqlite-41ewvc`. Do not open a
   PR unless the user asks. Remove this `HANDOFF.md` (or trim it to a short
   "maintenance" note) once stage 2 is complete.

## Notes / gotchas

- The site returns **403 to non-browser user agents** — the scraper already sends
  a browser `User-Agent`; keep it.
- Be polite: keep the default `--delay` (1s) for the full build; the full
  compendium is ~40+ seasons and tens of thousands of puzzles.
- A 403 mid-run raises `EgressBlockedError` and the CLI exits with code `2` and an
  actionable message — that means egress/UA, not a code bug.
- Design rationale and the full schema are in `README.md`; every function in
  `wheeldb.py` has a docstring explaining what it does and why.

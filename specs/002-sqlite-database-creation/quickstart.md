# Quickstart: SQLite Puzzle Database

Validation/run guide for the season-ingest feature. Proves the feature works
end-to-end without touching the live site (offline fixtures + a temporary
database). Implementation details live in [tasks.md](tasks.md) once generated;
the contracts are in [contracts/](contracts/).

## Prerequisites

- Python 3.11+ with the project installed in editable mode:
  ```bash
  py -m pip install -e .[dev]
  ```
- The existing season-page fixtures under `tests/fixtures/`
  (`compendium1.html`, `compendium20.html`, `compendium42.html`).
- No network access required; no new third-party dependency (storage uses the
  stdlib `sqlite3`).

## Run the offline test suite (primary validation)

Per Constitution Principle III, the offline suite is the source of truth.

```bash
py -m pytest tests/unit/test_storage.py tests/unit/test_ingest_args.py tests/integration/test_ingest.py -ra
```

Expected: all pass. Use `--print-puzzles` only when you intentionally want
solutions in the log (test boundary, Principle II/V).

### Scenarios these tests must cover (maps to spec)

| Scenario | Asserts | Spec |
|----------|---------|------|
| Ingest a single fixture season into a `tmp_path` DB | one row per parsed puzzle; all six attributes + `puzzle_number`/`puzzle_type` correct | US1 / SC-001, SC-002 |
| Re-ingest the same season | row count unchanged; summary shows `updated`, not `added` | US2 / SC-003 |
| Ingest a range over multiple fixture seasons | rows for every season in range; none outside it | US3 |
| Bounded fetch (spy fetcher records requested seasons) | only the requested season(s) fetched | FR-008a / SC-008 |
| Best-effort range with one unretrievable season | other seasons committed; `skipped` lists the bad one; DB has only committed seasons | FR-011 / SC-009 |
| `parse_season_arg` table | `"40"`,`"37-40"`,`"40-40"` accepted; `"40-37"`,`""`,`"abc"`,`"-5"` rejected | FR-008/FR-008b / SC-007 |
| Data error (a puzzle whose round yields no number) | run raises (halts), the offending season's rows unchanged | FR-010 / SC-006 |
| Single-season retrieval failure | returns summary with `skipped=[season]`, DB unchanged, no raise | FR-011 |
| First run with no DB file present | DB file created, schema present | FR-005 / SC-005 |
| CLI summary | stdout shows counts/seasons/source URLs; contains no solution | FR-009 / SC-004 |

## Manual end-to-end check against a fixture (no network)

Drive `ingest_seasons` with the offline `FixtureFetcher`, writing to a throwaway
database, then inspect it with the `sqlite3` CLI:

```bash
py - <<'PY'
from wheeldb.ingest import ingest_seasons
from tests.conftest import FixtureFetcher   # offline fetcher (seasons 1, 20, 42)

summary = ingest_seasons("42", db_path="scratch.sqlite", fetcher=FixtureFetcher())
print(summary.seasons, summary.added, summary.updated, summary.total)
PY

# Verify rows landed and derived columns are populated (no solutions printed by the tool itself):
sqlite3 scratch.sqlite "SELECT season, episode, round, puzzle_number, puzzle_type FROM puzzles LIMIT 5;"
sqlite3 scratch.sqlite "SELECT COUNT(*) FROM puzzles;"

# Idempotency: re-run and confirm the count does not grow.
py -c "from wheeldb.ingest import ingest_seasons; from tests.conftest import FixtureFetcher; print(ingest_seasons('42', db_path='scratch.sqlite', fetcher=FixtureFetcher()))"
sqlite3 scratch.sqlite "SELECT COUNT(*) FROM puzzles;"   # unchanged

rm scratch.sqlite
```

> Note: the manual `SELECT solution ...` would reveal answers — that is the
> database's purpose and is the user opting in at the SQLite prompt, not the
> `wheeldb` CLI printing spoilers.

## CLI smoke check (live — optional)

Only against the real site, honoring the politeness delay:

```bash
wheeldb ingest 40 --db wheeldb.sqlite
# → "Ingested season 40 into wheeldb.sqlite / Puzzles: N added, 0 updated (N total) / Source: ...compendium40"
wheeldb ingest 37-40 --db wheeldb.sqlite
```

Confirm stdout shows counts, seasons, and source URLs — and **no** puzzle
solutions (FR-009).

## Definition of done (validation)

- The scenarios table above is fully green offline.
- A re-run never increases the row count (idempotent, SC-003).
- A data error halts the run and leaves the offending season's rows unchanged
  (SC-006, FR-010); in a range, seasons committed earlier are retained.
- A range with one unretrievable season still commits the others and reports the
  skipped season (best-effort, FR-011/SC-009); each season is all-or-nothing
  (FR-011a).
- CLI stdout contains zero solutions (SC-004); only the requested seasons are
  fetched (SC-008).

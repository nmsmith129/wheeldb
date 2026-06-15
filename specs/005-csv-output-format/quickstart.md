# Quickstart / Validation: CSV Output Format

Runnable scenarios that prove the feature works end-to-end. All use saved fixtures
— no live network, no persistent file (Constitution I & III). Implementation detail
lives in [contracts/](contracts/) and [data-model.md](data-model.md); this is a
run/validation guide.

## Prerequisites

- Repo installed for development (see `requirements-dev.txt`).
- Run the suite with `py -m pytest` (test-first: write each test and watch it fail
  before implementing — CLAUDE.md).

## Scenario 1 — Ingest one season to CSV (US1, FR-003)

```
wheeldb ingest 42 --format csv --db out.sqlite --from-dir tests/fixtures
```

Expected:
- A file `out.csv` is created (extension swapped per FR-002a).
- First line is exactly:
  `season,episode,date,puzzle_type,puzzle_number,category,solution,flags`
- One data row per puzzle; columns in the contracted order.
- stdout reports `... into out.csv`, `N added, 0 updated (N total)`, and the
  source URL — and contains **no** solution text.

## Scenario 2 — Re-ingest is idempotent (US2, FR-004/FR-005)

Run Scenario 1 twice against the same `out.csv`. Expected:
- Row count is unchanged after the second run (no duplicates).
- Summary reports `0 added, N updated (N total)` on the second run.
- A changed source value (e.g. category) overwrites the matching row in place; all
  other rows are untouched.

## Scenario 3 — Default is still SQLite (FR-002)

```
wheeldb ingest 42 --db out.sqlite --from-dir tests/fixtures
```

Expected: `out.sqlite` is written exactly as before; no `.csv` file is produced.

## Scenario 4 — Header mismatch halts, file untouched (FR-012)

Pre-create `out.csv` with a wrong header (e.g. reordered columns), then run
Scenario 1. Expected:
- Exit code 2; stderr shows a database error.
- `out.csv` is byte-for-byte unchanged.

## Scenario 5 — Special characters round-trip (FR-007, SC-004)

Ingest a season whose data includes a category/solution containing a comma, a
quote, and (if present in fixtures) a newline. Re-read the CSV and confirm every
field equals its original value, and `flags` decodes back to the original list.

## Scenario 6 — Best-effort range to CSV (US3, FR-008)

```
wheeldb ingest 41-42 --format csv --db out.sqlite --from-dir <dir missing season 41>
```

Expected: season 42 rows are present in `out.csv`, season 41 is reported as
skipped, exit code 2, and the summary matches the SQLite path for the same input.

## Test mapping

| Scenario | Test location |
|----------|---------------|
| 1, 2, 3, 6 | `tests/integration/test_ingest.py` (CSV cases) |
| 4 | `tests/unit/test_csv_storage.py` (header validation) + integration |
| 5 | `tests/unit/test_csv_storage.py` (round-trip) |
| round reconstruction | `tests/unit/test_models.py` |
| `.csv` path derivation | `tests/unit/test_csv_path.py` |

## Acceptance

The feature is done when every scenario above passes through the offline suite,
the SQLite path is byte-for-byte unaffected, and no non-test code path prints a
solution.

# Quickstart: Episode Puzzle Parser

A validation/run guide proving the feature works end-to-end. Implementation
details live in `tasks.md` and the contracts; this file is about *running and
verifying*.

## Prerequisites

- Python 3.11+
- Install dependencies: `requests`, `beautifulsoup4`, `pytest`
  ```bash
  pip install -e .          # or: pip install requests beautifulsoup4 pytest
  ```

## Validate offline (primary — no network)

The offline test suite over saved fixtures is the source of truth for
correctness (Constitution I & III).

```bash
pytest                      # all tests, fully offline (HTTP layer mocked)
```

Expected: all tests pass, touching no network. Coverage spans early (S1), middle
(S20), and recent (S42) era fixtures.

### Print parsed puzzles during tests (FR-012 / Principle V)

```bash
pytest --print-puzzles tests/integration/test_extract_episode.py
```

Expected: each parsed puzzle's attributes — including its `solution` — are
printed to the test log. Without the flag, solutions are NOT printed.

## Validate the library API

See [contracts/library-api.md](contracts/library-api.md). Against the documented
example episode (S42 #8011), `extract_episode(8011)` returns three puzzles:

| solution | category | round | season | episode |
|----------|----------|-------|--------|---------|
| OPENING NIGHT | Show Biz | T1 | 42 | 8011 |
| ANIMATED SHORT ATTENTION SPAN | Before & After | R2 | 42 | 8011 |
| DIGITAL FOOTPRINT | Thing | BR | 42 | 8011 |

(In the offline test this runs against `tests/fixtures/compendium42.html`.)

Edge checks:
- `extract_episode(<nonexistent>)` → `[]`, no error (FR-010).
- A retrieval failure (e.g. HTTP 403) → `RetrievalError`, not an empty list
  (FR-011).

## Validate the CLI (spoiler-free — Principle II)

See [contracts/cli.md](contracts/cli.md).

```bash
wheeldb episode 8011
```

Expected stdout (counts + provenance only, NO solutions):

```text
Episode 8011 (Season 42): 3 puzzles found
  Rounds: T1, R2, BR
  Source: https://buyavowel.boards.net/page/compendium42
```

Verify: no puzzle solution text appears anywhere in stdout.

## Acceptance mapping

| Spec item | Validated by |
|-----------|--------------|
| FR-001/005, SC-002 | library API example above + integration test |
| FR-003 (six attributes), data-model | `test_models.py`, `test_extract_episode.py` |
| FR-006/007, SC-004 (normalization) | `test_normalize.py`, `test_parser.py` |
| FR-009, SC-003 (era coverage) | S1 / S20 / S42 fixtures |
| FR-010/011, SC-005 (not-found vs failure) | integration edge checks |
| FR-012/013, SC-006 (print option, no spoilers) | `--print-puzzles` on/off + CLI stdout check |

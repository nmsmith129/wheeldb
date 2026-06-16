# Quickstart / Validation: PowerPoint Puzzle Injection

Runnable scenarios that prove the feature works end-to-end. All run offline against
a fixture package and a temp store — no PowerPoint, no network (Constitution I & III).
Implementation detail lives in [contracts/](contracts/) and [data-model.md](data-model.md).

## Prerequisites

- A populated store covering the test season (ingest a fixture season first, e.g.
  `wheeldb ingest 42 --from-dir tests/fixtures`).
- The template `WheelofFortune6.4.pptm` present at the repo root (read-only input).
- The slot mapping spike (research Decision 4) completed so `SLOT_MAPPING` is
  populated. Run `py -m pytest` test-first: write each test and watch it fail before
  implementing (CLAUDE.md).

## Scenario 1 — Generate a game (US1, FR-003/005)

```
wheeldb game 42 --db out.sqlite --seed 7
```

Expected:
- `games/wof001.pptm` is created (smallest unused three-digit number).
- stdout reports `Created games/wof001.pptm from season 42` and `4 Round, 3 Toss-Up,
  1 Bonus Round (8 total)` — and contains **no** solution or category text.
- The original `WheelofFortune6.4.pptm` is byte-unchanged.

## Scenario 2 — Macros / package preserved (FR-004/SC-004)

Unzip the generated `games/wof001.pptm` and the template and compare parts. Expected:
- `ppt/vbaProject.bin` is byte-identical between template and output.
- Every part except the edited slide XML parts is byte-identical.

## Scenario 3 — Correct types in correct slots (US3, FR-005/006/007)

Read back the eight mapped slots from the generated file (behind the test boundary).
Expected: slots 1–4 hold Round solutions, 5–7 hold Toss-Up solutions, 8 holds a Bonus
Round solution; the eight puzzles are distinct.

## Scenario 4 — Numbering never overwrites (FR-003)

Generate twice. Expected: second run creates `games/wof002.pptm`; `wof001.pptm` is
untouched. Delete `wof001.pptm`, generate again → the gap is reused (`wof001.pptm`).

## Scenario 5 — Seeded reproducibility (FR-012/SC-006)

Generate two games from the same season with `--seed 7`. Expected: the eight selected
puzzles (and their slots) are identical. With different/no seed, the lineup varies.

## Scenario 6 — Insufficient puzzles errors cleanly (FR-010)

Point at a season with fewer than 3 Toss-Up puzzles. Expected: exit 2; stderr names
the short type and counts (no puzzle content); no game file is created.

## Test mapping

| Scenario | Test location |
|----------|---------------|
| 1, 4, 6 | `tests/integration/test_game.py` |
| 2 | `tests/unit/test_pptx_inject.py` (part-preservation) |
| 3 | `tests/unit/test_pptx_inject.py` + `tests/unit/test_gamegen.py` |
| 5 | `tests/unit/test_gamegen.py` (seeded selection) |
| `puzzles_for_season` | `tests/unit/test_storage.py` |

## Acceptance

Done when every scenario passes offline, the template (incl. `vbaProject.bin`) is
unaffected, and no operator output reveals a solution or category.

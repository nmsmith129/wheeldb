# Phase 1 Data Model: PowerPoint Puzzle Injection

This feature introduces no new persisted entity. It reuses the existing `Puzzle`
(see features 001/002) and works over the OOXML package. The "entities" here are the
in-memory shapes the generator passes between selection and injection.

## Reused entity

- **Puzzle** (`wheeldb.models.Puzzle`): solution, category, date, season, episode,
  round, flags, plus derived `puzzle_type` (`Round` / `Toss-Up` / `Bonus Round`) and
  `puzzle_number`. Read from the store; only `solution` and `category` are written
  into the game. **Unchanged.**

## New in-memory structures

### GameRequest

The inputs of one generation run.

| Field | Meaning | Source / validation |
|-------|---------|---------------------|
| `season` | season number to draw puzzles from | host-supplied; must exist in the store (else `GameError`) |
| `seed` | optional RNG seed for reproducible selection | host-supplied; `None` → system entropy (FR-012) |
| `store_path` | which ingested SQLite store to read | reuses the ingest `--db` convention (CSV source deferred to feature 005) |
| `games_dir` | output directory | defaults to `games/`; created if absent |

### SlotPlan

The fixed shape of a game — eight ordered slots and the puzzle type each requires.

| Slot | Type required | Count |
|------|---------------|-------|
| 1–4 | Round | 4 |
| 5–7 | Toss-Up | 3 |
| 8 | Bonus Round | 1 |

- A `SlotPlan` maps each slot index (1–8) to the selected `Puzzle`. Built by sampling
  without replacement per type from the season's puzzles (Decision 2/5). All eight
  puzzles are distinct (FR-007).

### SlotMapping (in `pptx_inject`)

The static table discovered by the spike (research Decision 4): for each slot index,
a **stable anchor** for the **solution** run and the **category** run — a content
placeholder token (preferred) or a unique `(slide part, shape name)` pair, never a
positional index. Read-only data; the single source of truth for where text is
written, and what makes injection robust to template edits (a wheel wedge, restyle,
or PowerPoint re-save does not move the anchors).

## Validation rules

| Rule | Source | Behavior on violation |
|------|--------|-----------------------|
| Season must be present in the store | FR-008 | `GameError`, no file written |
| Season must hold ≥4 Round, ≥3 Toss-Up, ≥1 Bonus Round | FR-010 | `GameError` naming the short type/count, no file |
| Eight selected puzzles are distinct | FR-007 | guaranteed by per-type sampling without replacement |
| Output number in `001–999` available (empty folder → `wof001`) | FR-003/FR-011 | `GameError` if all used; never overwrite |
| Template present and readable | Edge cases | `GameError`, no file written |
| Same season + same seed → same SlotPlan | FR-012/SC-006 | deterministic selection |

## Package transformation (state)

```
read template package (all parts) ──► build SlotPlan (select per type)
        │                                      │
        │  (template missing → GameError)      ▼
        │                          for each slot: locate runs via SlotMapping,
        │                          set solution + category text in slide XML
        ▼                                      │
  copy every untouched part byte-for-byte ◄────┘
  (vbaProject.bin, rels, media, content-types)
        │
        ▼
  write games/wof[N].pptm  (atomic: temp file then rename; never overwrite)
```

No operator-facing output carries solution or category text (Decision 6/7).

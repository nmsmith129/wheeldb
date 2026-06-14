# Phase 1 Data Model: Episode Puzzle Parser

Derived from the spec's Key Entities and Functional Requirements, plus the three
clarifications and FORMAT.md normalization rules.

## Entity: Puzzle

One Wheel of Fortune puzzle from one round of one episode. This is the object the
feature returns (FR-003). It is the only persisted-shape entity; Episode and
Season are conceptual groupings, not separate stored objects this feature.

### Required attributes (the six named in the spec)

| Attribute | Type | Description | Normalization (source → value) |
|-----------|------|-------------|--------------------------------|
| `solution` | `str` | The puzzle answer text. | PUZZLE cell → strip surrounding double quotes (straight or curly) + trim. Remains ALL CAPS as on the source. |
| `category` | `str` | Puzzle category, Title Case. | CATEGORY cell → trim. |
| `date` | `str` | Original air date. ISO `YYYY-MM-DD` when parseable; raw source text otherwise (FR-015, clarification Q3). | DATE cell → strip trailing `*` → parse `M/D/YY` with year pivot (`>=83`→19xx else 20xx) → ISO; else keep raw. |
| `season` | `int` | Season number the episode belongs to. | From the season page (`compendium{N}`) the episode was found on (FR-008). |
| `episode` | `int` | Global episode number. | The requested episode number; equals EP# cell with leading `#` stripped. |
| `round` | `str` | Clean raw round code (clarification Q2). | ROUND cell → strip trailing `*`/`^` → e.g. `T1`, `R2`, `BR`. |

### Derived / auxiliary attributes (not part of the required six)

| Attribute | Type | Description |
|-----------|------|-------------|
| `round_name` | `str` | Readable expansion of `round` (`T1`→`Toss-Up 1`, `R2`→`Round 2`, `BR`→`Bonus Round`). Derived on demand from `round`. |
| `puzzle_type` | `str` | Coarse type from the round's leading letter: `T*`→`Toss-Up`, `R*`→`Round`, `BR`→`Bonus Round`. |
| `flags` | list of (column, symbol) | Any `*`/`^` annotations seen, with the column they came from (date vs round). Preserved per FORMAT.md; empty when none. |

### Validation rules

- `solution` MUST be non-empty after trimming; a row with an empty PUZZLE cell is
  malformed and is skipped (logged in debug output), not returned.
- `season` MUST equal the page number the row was parsed from.
- `episode` MUST equal the requested episode number for every returned puzzle.
- `round` MUST be free of trailing `*`/`^`; `date` MUST be free of trailing `*`.
- A puzzle is uniquely identified by **(season, episode, round)**, with
  `solution` as a tie-breaker against a rare malformed/duplicated round label
  (FORMAT.md §"Proposed uniqueness key"). Two rows that differ only by a
  duplicated round label MUST remain two distinct puzzles, not be collapsed.

### Ordering

Within a returned episode, puzzles are ordered by round as they aired, i.e. in
the order the rows appear on the season page (FR-005). No re-sorting is applied.

## Conceptual grouping: Episode

- Identified by its global `episode` number; belongs to exactly one `season`.
- Contains an ordered set of `Puzzle` objects (one per round played).
- Not a stored object; it is the query key. `extract_episode(n)` returns the
  episode's puzzles, or an empty list if `n` appears in no season (FR-010).

## Conceptual grouping: Season

- A numbered season (`1`–`43` as of June 2026); its compendium page
  (`compendium{N}`) holds all puzzles for that season in one table.
- Supplies the `season` value and the rows from which puzzles are parsed.
- The lookup searches seasons to find the one containing the requested episode
  (FR-004); a season is not returned as an object.

## State transitions

None. Puzzles are immutable value objects produced by parsing; there is no
lifecycle/state machine in this feature.

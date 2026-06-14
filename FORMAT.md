# buyavowel.boards.net — Puzzle Compendium Format

Findings from inspecting the [Buy A Vowel Boards Puzzle
Compendium](https://buyavowel.boards.net/page/compendiumindex), for the purpose
of scraping every Wheel of Fortune puzzle into a queryable database.

**Verified against**: the index page, plus season pages 1 (1983–84), 20
(2002–03), and 42 (2024–25) — i.e. early, middle, and recent eras. The format is
consistent across all three.

## Site structure

The compendium is a set of static wiki-style pages on a ProBoards forum. There
are two page types relevant to scraping:

1. **Index page** — `https://buyavowel.boards.net/page/compendiumindex`
   - A hub linking to one page per season, laid out as a grid of image tiles
     (seasons grouped in rows of five: 1–5, 6–10, …, 41–43).
   - Also links to ancillary analysis pages (frequency data, "Choices 50",
     schedules) that are **not** puzzle data and should be ignored.

2. **Season pages** — `https://buyavowel.boards.net/page/compendium{N}`
   - `{N}` is the season number, `1`–`43` as of June 2026 (1983 → present).
   - Each page holds **all puzzles for that season** in a single table.
   - The full set of season URLs can be derived two ways:
     - Scrape the index and follow every `/page/compendium{N}` link, or
     - Generate `compendium1`…`compendiumN` directly (simpler, but relies on the
       contiguous numbering holding).

## Per-season puzzle table

Every season page presents puzzles in **one HTML `<table>`** with five columns,
in this fixed order:

| PUZZLE | CATEGORY | DATE | EP# | ROUND |
|--------|----------|------|-----|-------|

Each **row is one puzzle**. Rows for the same episode repeat the DATE and EP#
values and appear consecutively, ordered by round within the episode, and
episodes are ordered by air date. This means a row is self-contained — every row
carries its own season (from the page), date, episode, round, category, and
solution — so no cross-row state is required to parse it.

### Column definitions

| Column | Meaning | Example values |
|--------|---------|----------------|
| **PUZZLE** | The puzzle solution, in ALL CAPS. Sometimes wrapped in straight double quotes (`"…"`) on later-era pages; unquoted on early ones. | `BURT LANCASTER`, `"OPENING NIGHT"`, `"MALCOLM IN THE MIDDLE AGES"` |
| **CATEGORY** | Puzzle category, Title Case. | `Person`, `Phrase`, `Thing`, `Before & After`, `On the Map`, `Show Biz`, `Song Lyrics`, `Event`, `Place` |
| **DATE** | Original air date, U.S. `M/D/YY` (no zero-padding). May carry a trailing symbol (see below). | `9/19/83`, `9/2/02`, `9/9/24` |
| **EP#** | Episode number, prefixed with `#`. Width grows over time. | `#1`, `#5` (early) → `#3706`, `#8011` (recent) |
| **ROUND** | Round code (see legend). May carry a trailing symbol. | `R1`, `T1`, `BR`, `R3*`, `R2^` |

### ROUND code legend

| Code | Round | Notes |
|------|-------|-------|
| `T1`–`T5` | Toss-Up rounds 1–5 | Did not exist in the earliest seasons; introduced as the show added toss-ups. |
| `R1`–`R5` | Main game rounds 1–5 | Early seasons typically only reach `R4`. |
| `BR` | Bonus Round | The final round. |

To derive a coarse `puzzle_type` for sorting (matching the prior schema), map the
**leading letters** of the code: `T*` → `Toss-Up`, `R*` → `Round`, `BR` →
`Bonus Round`.

### Annotation symbols

Some DATE and ROUND cells carry a trailing symbol. These are **meaningful but
context-dependent** and should be parsed off the value (and ideally preserved in
a notes/flags field rather than discarded):

- **`*` (asterisk)** — overloaded by era:
  - On **dates in Season 1**: "bicycling" — the episode aired on no consistent
    national date (stations aired at their own whim).
  - On a **round** (e.g. `R3*`): prize puzzle indicator.
  - Treat `*` as a flag whose meaning depends on the column and era; do not
    assume a single semantics.
- **`^` (caret)** on a round (e.g. `R2^`) — a special/trivia puzzle variant.
  Exact distinction is not documented on the source pages.

When normalizing, **strip these symbols** to get the clean date/round value, and
record their presence separately.

## Era variations (all within the same 5-column layout)

| Aspect | Early (S1) | Recent (S42) |
|--------|-----------|--------------|
| Round set | `R1`–`R4`, `BR` (no toss-ups) | `T1`–`T5`, `R1`–`R5`, `BR` |
| Episode # | `#1`, `#5` | `#8011` |
| Puzzle quoting | usually unquoted | wrapped in `"…"` |
| Asterisk meaning | bicycling (on dates) | prize puzzle (on rounds) |

The column count, order, and headers do **not** change — only the value ranges
and annotations do.

## Recommended extraction approach

1. **Discover seasons**: fetch the index, collect `href`s matching
   `/page/compendium\d+`, dedupe, sort numerically. (Fallback: iterate
   `compendium1..N`.)
2. **Per season page**: locate the puzzle `<table>`, skip the header row
   (`PUZZLE/CATEGORY/DATE/EP#/ROUND`), and read each `<tr>` as one puzzle.
3. **Per row**, normalize:
   - `solution` ← PUZZLE, strip surrounding quotes and trim.
   - `category` ← CATEGORY, trim.
   - `air_date` ← DATE: strip trailing `*`; parse `M/D/YY` to ISO `YYYY-MM-DD`
     (2-digit year pivot: `>=83` → 19xx, else 20xx). Keep raw text if unparseable.
   - `episode` ← EP#, strip leading `#` (keep as text — values are clean ints
     today but treat defensively).
   - `round_name` ← expand the ROUND code to a readable name
     (`T1` → `Toss-Up 1`, `R2` → `Round 2`, `BR` → `Bonus Round`), after
     stripping `*`/`^`.
   - `puzzle_type` ← coarse type from the round's leading letters (above).
   - `flags` ← record any `*`/`^` seen, with the column they came from.
   - `season` ← from the page number; `source_url`, `scraped_at` ← provenance.

## Proposed uniqueness key

A puzzle is uniquely identified by **(season, episode, round)**. Adding
`solution` to the key (as the prior schema did) guards against the rare case of a
malformed/duplicated round label. Recommended unique constraint:
`(season, episode, round_name, solution)`.

## Open questions / things to confirm against raw HTML

These need verification against the actual page markup (the WebFetch tooling
returns rendered/markdownified text, not raw tags):

- **Exact table markup**: tag/class/id of the puzzle table, so a selector can
  target it and skip navigation/other tables on the page.
- **Whether a season is one table or several** (e.g. one table per episode). The
  repeating EP# column is consistent with a single season-wide table, but
  confirm.
- **Multi-table pages**: some pages may contain extra tables (legends, notes);
  the scraper must select the puzzle table specifically, not the first `<table>`.
- **Quote characters**: straight vs. curly quotes around puzzle text, to strip
  correctly.
- **403 to non-browser agents**: per prior project notes, the site returns HTTP
  403 unless a real browser `User-Agent` is sent — required for any scraper.

## Quick reference — one example episode (S42, EP #8011, 9/9/24)

```
PUZZLE                           CATEGORY        DATE     EP#     ROUND
"OPENING NIGHT"                  Show Biz        9/9/24   #8011   T1
"ANIMATED SHORT ATTENTION SPAN"  Before & After  9/9/24   #8011   R2
"DIGITAL FOOTPRINT"              Thing           9/9/24   #8011   BR
```

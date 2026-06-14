# Phase 0 Research: Episode Puzzle Parser

No `NEEDS CLARIFICATION` markers remained in Technical Context after
`/speckit-clarify`. This document records the technology and approach decisions
that the design depends on.

## 1. HTTP retrieval with a real browser User-Agent

- **Decision**: Use `requests` with an explicit desktop-browser `User-Agent`
  header and a fixed politeness delay between season-page fetches. Treat an HTTP
  403 (or any non-200) as a *retrieval failure* (raise a typed error), distinct
  from "episode not found".
- **Rationale**: FORMAT.md documents that the site returns HTTP 403 to
  non-browser agents (Open Questions §). The constitution requires respectful
  scraping (politeness delay, browser UA, no parallel hammering). `requests` is
  the simplest synchronous client and is trivially mockable in tests.
- **Alternatives considered**: `urllib` (more boilerplate for headers/sessions);
  `httpx`/async (concurrency conflicts with the serialized-politeness constraint
  and adds complexity for no benefit at this scale).

## 2. HTML table parsing and puzzle-table selection

- **Decision**: Parse with `beautifulsoup4`. Select the puzzle table by matching
  its header row signature (`PUZZLE / CATEGORY / DATE / EP# / ROUND`) rather than
  by document position, so navigation/legend/notes tables are skipped. Read each
  subsequent `<tr>` as one puzzle (5 cells, fixed order).
- **Rationale**: FORMAT.md warns pages may contain extra tables and that the
  scraper "must select the puzzle table specifically, not the first `<table>`".
  Header-signature matching is robust to multi-table pages and to position
  changes. The 5-column order is fixed across all eras.
- **Alternatives considered**: `pandas.read_html` (convenient but weak at
  multi-table disambiguation and at preserving/stripping the surrounding quote
  characters precisely); positional/first-table selection (brittle per FORMAT.md).

## 3. Episode → season lookup strategy (from clarification)

- **Decision**: The parser owns the lookup. It walks season pages (`compendium1`,
  `compendium2`, …) and returns the rows whose normalized `EP#` equals the
  requested episode number. It short-circuits: once a page contains the episode
  (or once a page's episode range has passed the target), it stops fetching
  further seasons. No caller-supplied season; no hand-maintained mapping.
- **Rationale**: Clarification Q1 selected "search season pages and match
  `EP#`". FORMAT.md notes episode numbers are globally unique and monotonic with
  air date, which makes a containing-season early-stop safe while avoiding a
  brittle hardcoded episode→season map (FORMAT.md cautions numbering may drift).
- **Alternatives considered**: Require caller to pass the season (rejected by
  clarification — pushes lookup burden onto callers); scrape the index page for
  the season list first (extra fetch; season URLs are derivable as
  `compendium{N}`); hardcoded episode-range map (brittle as the show airs more
  episodes).

## 4. Value normalization (FORMAT.md §"Recommended extraction approach")

- **Decision**: A single `normalize` module is the source of truth:
  - `solution` ← strip surrounding straight/curly double quotes + trim.
  - `category` ← trim.
  - `date` ← strip trailing `*`; parse `M/D/YY` to ISO `YYYY-MM-DD` with a
    2-digit-year pivot (`>=83` → 19xx, else 20xx); keep raw text if unparseable.
  - `round` ← strip trailing `*`/`^`; keep the clean raw code (`T1`/`R2`/`BR`).
  - `episode` ← strip leading `#`.
  - Annotation flags (`*`/`^`) and the column they came from are recorded
    separately (not among the six required attributes).
- **Rationale**: Matches FORMAT.md normalization rules and the three
  clarifications (round = clean code, date = ISO-or-raw). Centralizing satisfies
  Principle IV (no duplicated normalization).
- **Alternatives considered**: Inline normalization at each call site (rejected —
  drifts apart, violates Reuse-Before-Creation).

## 5. Offline, debuggable testing

- **Decision**: Capture representative season-page HTML fixtures for early (S1),
  middle (S20), and recent (S42) eras. Mock the `fetch` layer in tests so the
  parser/lookup run entirely offline. Provide a pytest option
  (`--print-puzzles`, exposed via `conftest.py`) that, when set, prints each
  parsed puzzle's attributes (including solution) to the test log. Tests print
  inputs/expected/actual at assertion points.
- **Rationale**: Principles I (offline), III (test-first, fixtures), V (debuggable
  output). FORMAT.md verified the format against exactly these three eras, so they
  are the natural fixtures. The print option satisfies FR-012 and doubles as the
  Principle V debug surface; gating it behind a test-only flag keeps Principle II
  (no spoilers in normal operation).
- **Alternatives considered**: Hitting the live site in tests (rejected —
  violates offline principle, flaky, impolite); always-on printing (rejected —
  would leak solutions outside the test boundary).

## 6. Date year-pivot edge

- **Decision**: 2-digit year `YY`: if `YY >= 83` → `19YY`, else `20YY`. Season 1
  began 1983, so 83 is the earliest valid year; values 00–82 map to the 2000s.
- **Rationale**: FORMAT.md specifies this pivot explicitly. Safe through the
  current era and for decades forward.
- **Alternatives considered**: Per-season year derivation (more complex; the
  pivot is unambiguous given the show's 1983 start).

**Output**: All Technical Context items resolved; no open `NEEDS CLARIFICATION`.

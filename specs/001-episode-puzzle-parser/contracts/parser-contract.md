# Contract: Parser & Normalization

Defines how raw season-page HTML becomes `Puzzle` objects. Centralized in
`parser.py` + `normalize.py` (single source of truth — Principle IV).

## Table selection

```python
def find_puzzle_table(html: str) -> Table:
    """Locate the puzzle table within a season page.

    Selects the table whose header row matches the signature
    PUZZLE / CATEGORY / DATE / EP# / ROUND, skipping navigation, legend, and
    notes tables.

    Parameters:
        html: raw HTML of a compendium season page.
    Returns:
        The puzzle table (header + data rows).
    Raises:
        ParseError: no table matching the expected header signature was found.
    """
```

**Guarantee**: selection is by header signature, never by position (FORMAT.md
warns of multi-table pages).

## Row parsing

```python
def parse_rows(table: Table, season: int) -> list[Puzzle]:
    """Parse each data row of a puzzle table into a Puzzle.

    Parameters:
        table: the puzzle table from find_puzzle_table.
        season: the season number for the page (sets Puzzle.season).
    Returns:
        One Puzzle per data row, in source (round) order. Header row skipped.
    """
```

**Guarantees**: header row skipped; one `Puzzle` per data row; order preserved;
rows with an empty PUZZLE cell are skipped (logged), not returned.

## Normalization (single source of truth)

| Function | Input → Output | Rule |
|----------|----------------|------|
| `normalize_solution(s)` | `"OPENING NIGHT"` → `OPENING NIGHT` | strip surrounding straight/curly double quotes + trim |
| `normalize_category(s)` | `Before & After ` → `Before & After` | trim |
| `normalize_date(s)` | `9/9/24` → `2024-09-09`; `9/19/83` → `1983-09-19` | strip trailing `*`; parse `M/D/YY` with pivot (`>=83`→19xx else 20xx); raw text if unparseable |
| `normalize_round(s)` | `R3*` → (`R3`, flag `*`); `R2^` → (`R2`, flag `^`) | strip trailing `*`/`^`; return clean code + any flag |
| `normalize_episode(s)` | `#8011` → `8011` | strip leading `#`; to int |

Each function carries a docstring stating purpose, parameters, and return value
(Principle VI). Annotation flags returned by `normalize_date`/`normalize_round`
are collected into `Puzzle.flags` with their originating column.

## Error types

| Type | Raised when |
|------|-------------|
| `RetrievalError` | a season page cannot be fetched (HTTP 403, network) |
| `ParseError` | the puzzle table cannot be located on a fetched page |

A `ParseError`/`RetrievalError` is never silently turned into an empty result —
"episode not found" (empty list) only arises when pages parse cleanly but no row
matches the requested episode (FR-010 vs FR-011).

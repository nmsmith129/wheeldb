# Phase 0 Research: CSV Output Format

The spec was fully clarified before planning (two `/speckit-clarify` answers; no
`NEEDS CLARIFICATION` markers remain). This document records the design decisions
that resolve the requirement-quality gaps raised by the `checklists/csv.md`
checklist, so implementation and test design are unambiguous.

## Decision 1 — CSV module & dialect

- **Decision**: Use the standard-library `csv` module with the default `excel`
  dialect (comma delimiter, `"` quote char, `QUOTE_MINIMAL`), files opened with
  `newline=""` and written with an explicit `lineterminator="\n"`, encoded UTF-8.
- **Rationale**: `csv` handles embedded commas/quotes/newlines correctly out of
  the box (FR-007, SC-004); `newline=""` + a fixed terminator make round-trips
  byte-stable across platforms; no new dependency (Principle IV, Additional
  Constraints "Python with SQLite" stack stays intact).
- **Alternatives considered**: hand-rolled join/split (rejected — fails on
  embedded separators); pandas (rejected — heavy new dependency for a trivial
  table). *(Resolves CHK003.)*

## Decision 2 — Column set, order, and header

- **Decision**: Header and every data row use exactly, in order:
  `season, episode, date, puzzle_type, puzzle_number, category, solution, flags`.
  The header is always written (including a zero-row file).
- **Rationale**: Matches FR-003 verbatim (the user's seven fields plus the trailing
  `flags`). A fixed header is the contract used for the exact-match validation in
  Decision 6. *(Resolves CHK016, CHK019.)*

## Decision 3 — Field serialization (date, flags, empties)

- **Decision**: `season`, `episode`, `puzzle_number` are written as their integer
  text. `date` is written as the model's existing ISO `YYYY-MM-DD` string,
  verbatim. `flags` reuses the SQLite store's encoding exactly —
  `json.dumps([list(pair) for pair in puzzle.flags])` — so an empty flag tuple
  serializes to `[]`. `category`/`solution` are written as-is and quoted by the
  `csv` module only when needed.
- **Rationale**: Reusing the identical `date` string and `flags` JSON encoding
  guarantees parity with the SQLite product and a deterministic round-trip
  (SC-004). The CSV store never needs to parse `flags` back — it carries the cell
  through verbatim — so encoding and decoding cannot drift. *(Resolves CHK001,
  CHK002, CHK004.)*

## Decision 4 — De-duplication identity & round reconstruction

- **Decision**: The in-memory working set is an insertion-ordered dict keyed on
  `(season, episode, round)`. For a freshly ingested `Puzzle` the key uses
  `puzzle.round` directly (no reconstruction needed). For a row read back from an
  existing file, `round` is reconstructed from the `puzzle_type` + `puzzle_number`
  columns by a new pure helper `round_from_type_and_number()` added to `models.py`
  (the inverse of the existing `puzzle_type`/`puzzle_number` properties):
  `Bonus Round → BR`, `Toss-Up`+N → `TN`, `Round`+N → `RN`.
- **Rationale**: Keeps the canonical key shape identical to the SQLite primary key
  (FR-004) and the mapping in one module beside its forward counterpart
  (Principle IV). The forward/inverse pair is a bijection over valid codes, so the
  reconstructed key is stable. *(Resolves CHK012, CHK015 — see Decision 8.)*

## Decision 5 — Unrecognized type/number on read

- **Decision**: If an existing row's `puzzle_type`/`puzzle_number` pair does not map
  to a recognized round code, `round_from_type_and_number()` raises
  `PuzzleParseError`; the run halts on that season (the file is left untouched —
  see Decision 7), consistent with how the SQLite path treats an unrecognized round
  code.
- **Rationale**: A foreign/corrupt row is a data error, not a silent mismatch
  (FR-004 edge case). Reusing `PuzzleParseError` means the CLI already maps it to a
  clear error and a non-success exit. *(Resolves CHK005, CHK021.)*

## Decision 6 — Pre-existing file header validation

- **Decision**: On open, if the target file exists and is non-empty, its first row
  must equal the expected header exactly — same column names, same order, no extra
  or missing columns (compared after stripping a trailing newline only; no
  case-folding, no whitespace trimming inside names). Any mismatch raises
  `DatabaseError` and the file is left untouched. An empty/zero-byte file is treated
  as "no prior data" and is (re)written with the header on commit.
- **Rationale**: Exact match is the safest, most predictable rule (FR-012) and
  matches the spec's "reject rather than silently fall back" stance. Reusing
  `DatabaseError` keeps the CLI's existing exit-code mapping. *(Resolves CHK007 in
  part, CHK011.)*

## Decision 7 — Atomicity (transaction, commit, rollback)

- **Decision**: `CsvPuzzleStore` mirrors `PuzzleStore`'s `transaction()`
  contextmanager. At transaction entry it snapshots the in-memory dict; `upsert()`
  mutates the dict and returns `"added"`/`"updated"` relative to the dict's current
  contents; on a clean exit `commit()` rewrites the **entire** file from the dict
  (header + rows in insertion order) by writing a sibling temp file and
  `os.replace()`-ing it into place; on any exception `rollback()` restores the
  snapshot and the on-disk file is never touched for that season.
- **Rationale**: The atomic temp-file replace gives all-or-nothing per season
  (FR-009): a season either fully lands or the file stays exactly as it was, even
  if the process is interrupted mid-write (the partial temp file is discarded).
  Rewriting the whole file from the merged dict preserves earlier seasons (FR-004,
  edge "pre-existing file"). *(Resolves CHK006 — insertion order is preserved and
  new keys append; CHK014, CHK020.)*

## Decision 8 — Identity vs model uniqueness (consistency)

- **Decision**: The CSV de-dup identity is `(season, episode, round)`, matching the
  SQLite primary key — **not** the `Puzzle` dataclass's equality key of
  `(season, episode, round, solution)`. The plan and data-model state this
  explicitly so the two notions are not conflated.
- **Rationale**: The spec's Assumptions already fix `(season, episode, round)` as
  the stable identity for persistence; `solution` participates only in value
  equality of the in-memory object, not in storage identity. Documenting it removes
  the apparent conflict. *(Resolves CHK015, CHK013, CHK017 — within-run duplicate
  keys collapse last-wins and are counted once by the existing `ingest` `seen_keys`
  logic, identical to SQLite.)*

## Decision 9 — `--format` selection & output path derivation

- **Decision**: Add `--format {sqlite,csv}` to the `ingest` subparser (argparse
  `choices`), default `sqlite`; an unsupported value is rejected by argparse with a
  non-zero exit (FR-011). When `csv` is selected, derive the output path from the
  existing `--db` value via `pathlib.Path(db).with_suffix(".csv")`: a recognized
  extension is replaced (`wheeldb.sqlite → wheeldb.csv`), and a path with no
  extension has `.csv` appended (`wheeldb → wheeldb.csv`).
- **Rationale**: `argparse choices` gives the clear-error/no-silent-fallback
  behavior for free; `Path.with_suffix` is exactly the "swap extension, else
  append" rule of FR-002a. "Recognized extension" = whatever `Path.suffix` treats
  as the final dotted segment (e.g. `my.data.sqlite → my.data.csv`); this edge is
  documented in the contract. *(Resolves CHK008, CHK010, CHK022.)*

## Summary of resolved checklist gaps

| Checklist item | Resolved by |
|----------------|-------------|
| CHK001 flags encoding | Decision 3 (reuse JSON) |
| CHK002 empty flags | Decision 3 (`[]`) |
| CHK003 CSV dialect | Decision 1 |
| CHK004 date format | Decision 3 (ISO, verbatim) |
| CHK005 puzzle_type domain / Unknown | Decision 5 |
| CHK006 post-merge ordering | Decision 7 (insertion order, append) |
| CHK007 unreadable/invalid file | Decision 6 (header-validate; empty = no data) |
| CHK008 exit behavior | Decision 9 (argparse + existing mapping) |
| CHK010 "recognized extension" | Decision 9 (`Path.suffix`) |
| CHK011 exact header match | Decision 6 |
| CHK012 reconstruction mapping | Decision 4 |
| CHK013/CHK017 added/updated, within-run dup | Decision 8 |
| CHK014/CHK020 all-or-nothing, interrupted write | Decision 7 |
| CHK015/CHK016 identity & column consistency | Decisions 2, 8 |
| CHK018 identity collision on read | Decision 4 (bijection → equal keys merge last-wins) |
| CHK019 header-only first/zero-row | Decision 2 |
| CHK021 reconstruction failure | Decision 5 |
| CHK022 accepted formats | Decision 9 |
| CHK023/CHK024 assumptions | Carried from spec Assumptions; no change |

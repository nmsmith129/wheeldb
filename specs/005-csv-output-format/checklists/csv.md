# CSV Behavior Requirements Checklist: CSV Output Format

**Purpose**: Pre-plan gate validating that the spec's requirements for CSV
correctness/round-trip, idempotent in-place editing, and failure/edge handling are
complete, clear, consistent, and measurable before `/speckit-plan`.
**Created**: 2026-06-15
**Feature**: [spec.md](../spec.md)

**Note**: These items test the *requirements* (the English in the spec), not the
implementation. Each asks whether something is adequately specified.

## Requirement Completeness

- [x] CHK001 Is the serialization format of the `flags` cell explicitly specified (e.g., that it is JSON), rather than only described as "a single field"? [Completeness, Spec §FR-006]
- [x] CHK002 Is the representation of an empty/absent `flags` value defined so a round-trip is deterministic (e.g., empty list vs blank cell)? [Gap, Spec §FR-006]
- [x] CHK003 Is the CSV dialect (delimiter, quote character, quoting rules, line terminator, text encoding) specified well enough to guarantee the round-trip claim? [Gap, Spec §FR-007]
- [x] CHK004 Is the on-disk representation of the `date` field specified (format/string form written to the cell)? [Gap, Spec §FR-003]
- [x] CHK005 Are all possible `puzzle_type` values enumerated (including the "Unknown" case) so the column's domain is complete? [Completeness, Spec §FR-003/§FR-004]
- [x] CHK006 Is the post-merge row ordering of the output file specified (e.g., new rows appended, existing order preserved)? [Gap, Spec §FR-004]
- [x] CHK007 Are requirements defined for an existing target file that is unreadable or not valid CSV (distinct from a header mismatch)? [Gap, Spec §FR-012]
- [x] CHK008 Is the exit/return behavior on a non-success outcome (unknown format, header mismatch, data error) specified concretely rather than as "non-success"? [Completeness, Spec §FR-011/§FR-012]

## Requirement Clarity & Measurability

- [x] CHK009 Is "round-trips back to its exact original value" defined precisely enough to be objectively verified for every field type, including empty values? [Measurability, Spec §SC-004]
- [x] CHK010 Is "recognized extension" defined for the path-derivation rule, so it is unambiguous when `.csv` is appended versus when an extension is replaced? [Ambiguity, Spec §FR-002a]
- [x] CHK011 Is "exact header match" defined with respect to column names, order, case, and surrounding whitespace? [Clarity, Spec §FR-012]
- [x] CHK012 Is the round-reconstruction mapping stated as a complete, unambiguous inverse (Toss-Up N→`TN`, Round N→`RN`, Bonus Round→`BR`) covering every emitted `puzzle_type`/`puzzle_number` pair? [Clarity, Spec §FR-004]
- [x] CHK013 Are the "added" vs "updated" classifications defined relative to the file's prior contents (not just within the run)? [Clarity, Spec §FR-005]
- [x] CHK014 Is "left in its prior state for that season" (all-or-nothing) expressed as an observable, checkable guarantee for a single rewritten file? [Measurability, Spec §FR-009]

## Requirement Consistency

- [x] CHK015 Does the spec reconcile the de-duplication key `(season, episode, round)` with the model's stated uniqueness of `(season, episode, round, solution)`, so the intended identity is unambiguous? [Conflict, Spec §FR-004 / Assumptions]
- [x] CHK016 Are the column names used in FR-003, the Key Entities section, and the Assumptions section consistent with each other (same names, same order)? [Consistency, Spec §FR-003]
- [x] CHK017 Is the within-run duplicate-key behavior (collapse to one row, counted once) specified consistently with the SQLite path it claims parity with? [Consistency, Spec §FR-005]

## Edge Case & Failure Coverage

- [x] CHK018 Are requirements defined for two stored rows whose `puzzle_type`/`puzzle_number` reconstruct to the same round code (identity collision on read)? [Coverage, Gap]
- [x] CHK019 Is the header-only output requirement specified for both first-run and zero-puzzle cases? [Coverage, Spec Edge Cases]
- [x] CHK020 Are requirements defined for a process interrupted mid-write (e.g., partial/temp file), consistent with the all-or-nothing guarantee? [Edge Case, Gap, Spec §FR-009]
- [x] CHK021 Is the handling of a `puzzle_type`/`puzzle_number` pair that does not map to a recognizable round code specified as a halting data error (not a silent mismatch)? [Coverage, Spec Edge Cases / §FR-004]
- [x] CHK022 Are the set of accepted `--format` values enumerated, and is the rejection of any other value specified? [Coverage, Spec §FR-011]

## Dependencies & Assumptions

- [x] CHK023 Is the assumption that one CSV file holds all seasons (mirroring one SQLite DB) stated as a validated constraint rather than left implicit? [Assumption, Spec Assumptions]
- [x] CHK024 Is the "full parity = observable behavior parity" assumption scoped so the reader knows which behaviors are in-scope to verify (counts, idempotency, best-effort, all-or-nothing, no spoilers)? [Assumption, Spec Assumptions]

## Notes

- Check items off as the spec is updated to resolve each: `[x]`.
- Items marked `[Gap]`, `[Ambiguity]`, or `[Conflict]` are the highest-value to resolve before `/speckit-plan`, as they will otherwise surface as rework during implementation/test design.
- This checklist intentionally excludes SQLite-parity items beyond consistency cross-checks (parity was de-scoped for this checklist run).

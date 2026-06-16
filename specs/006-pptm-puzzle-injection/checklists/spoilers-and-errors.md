# No-Spoilers & Error-Handling Requirements Checklist: PowerPoint Puzzle Injection

**Purpose**: Pre-plan gate validating that the spec's no-spoilers guarantee and its
error/edge-handling requirements are complete, clear, consistent, and measurable
before `/speckit-plan`.
**Created**: 2026-06-15
**Feature**: [spec.md](../spec.md)

**Note**: These items test the *requirements* (the English in the spec), not the
implementation. Each asks whether something is adequately specified.

## No-Spoilers Requirement Quality

- [x] CHK001 Is "operator-facing output" defined precisely enough to scope the no-spoilers rule (e.g., stdout, stderr, logs, progress messages all in scope)? [Clarity, Spec §FR-009]
- [x] CHK002 Does the spec state what the generation step IS allowed to report (created file path, counts, slot placement) so "no spoilers" is verifiable against an allow-list rather than only a prohibition? [Completeness, Spec §FR-009]
- [x] CHK003 Is the no-spoilers guarantee defined to cover the category text as well as the solution, or is category disclosure intentionally permitted? [Ambiguity, Spec §FR-009 / Key Entities]
- [x] CHK004 Is it specified whether any spoiler may appear when an error is reported (e.g., an "insufficient puzzles" message must not name puzzles)? [Coverage, Gap, Spec §FR-009/§FR-010]
- [x] CHK005 Is the no-spoilers expectation reconciled with the fact that the generated game FILE necessarily contains solutions (the boundary is operator output, not the artifact)? [Consistency, Spec §FR-009 / Key Entities]
- [x] CHK006 Can "no puzzle solution is exposed during generation" be objectively measured (a clear pass/fail criterion for SC-005)? [Measurability, Spec §SC-005]
- [x] CHK007 Is the no-spoilers requirement traceable to the project's existing no-spoilers principle so its intent and scope are unambiguous? [Traceability, Spec §FR-009]

## Error & Edge-Handling Requirement Quality

- [x] CHK008 Are the conditions that constitute "the named season is not present" defined (absent entirely vs present but empty)? [Clarity, Spec §FR-008/§FR-010]
- [x] CHK009 Is the insufficient-puzzles threshold stated per type (≥4 Round, ≥3 Toss-Up, ≥1 Bonus) rather than as an aggregate count? [Completeness, Spec §FR-010 / Edge Cases]
- [x] CHK010 Is "report a clear error and produce no game file" specified as an observable, all-or-nothing outcome (no partial file left behind) for every error path? [Measurability, Spec §FR-010]
- [x] CHK011 Are requirements defined for the all-numbers-used case (`wof001`–`wof999`) as a bounded error rather than an overwrite or silent failure? [Coverage, Spec §FR-011 / Edge Cases]
- [x] CHK012 Is the missing-template case specified as a distinct error (template absent → clear error, no empty file)? [Completeness, Spec Edge Cases]
- [x] CHK013 Is the games-folder-absent behavior (create it before writing) specified unambiguously, including whether intermediate paths are created? [Clarity, Spec §FR-002 / Edge Cases]
- [x] CHK014 Is the smallest-unused-number rule defined for the gap case (a deleted `wof001.pptm` is reused before `wof003.pptm`) so numbering behavior is unambiguous? [Clarity, Spec §FR-003 / Edge Cases]
- [x] CHK015 Is it specified what counts as an "existing file" for numbering (only `wof[N].pptm` matches, or any file) so non-conforming names don't perturb selection? [Ambiguity, Spec §FR-003]
- [x] CHK016 Are requirements defined for when the seed is supplied but the season still cannot satisfy the type counts (error precedence: missing data vs determinism)? [Coverage, Gap, Spec §FR-010/§FR-012]
- [x] CHK017 Is each distinct failure mode (missing season, insufficient type counts, no number available, missing template) required to be distinguishable to the operator, rather than a single generic error? [Completeness, Spec §FR-010/§FR-011]
- [x] CHK018 Are the error paths consistent with the all-or-nothing guarantee — i.e., no error path partially populates or partially writes the game file? [Consistency, Spec §FR-001/§FR-010]
- [x] CHK019 Is concurrent generation (two runs racing for the same smallest number) addressed or explicitly out of scope? [Coverage, Gap]
- [x] CHK020 Is the distinctness requirement (FR-007) reconciled with the insufficient-puzzles threshold so a season with exactly the minimum counts is still satisfiable without reuse? [Consistency, Spec §FR-007/§FR-010]

## Dependencies & Assumptions

- [x] CHK021 Is the dependency on a populated ingested puzzle store (the season's puzzles must already be ingested) stated as a validated precondition for generation? [Assumption, Spec Assumptions]
- [x] CHK022 Is the assumption that the host enables macros (so the generated game runs) documented as a host responsibility rather than a tool guarantee? [Assumption, Spec Assumptions]

## Notes

- Check items off as the spec is updated to resolve each: `[x]`.
- Items marked `[Gap]`, `[Ambiguity]`, or `[Conflict]` are the highest-value to resolve before `/speckit-plan`.
- This checklist intentionally scopes to the no-spoilers guarantee and error/edge
  handling; puzzle-selection correctness and file-integrity mechanics beyond their
  error paths are out of scope for this run.
- **Resolution pass (2026-06-15)**: CHK005–007 and CHK008–015, CHK021–022 were
  already covered by existing spec text (FR-009, Key Entities, FR-002/003/010/011,
  Edge Cases, Assumptions) and are checked off as-is. CHK016–020 were genuine gaps;
  closed by adding **FR-014** (distinguishable failure modes), **FR-015** (fixed
  validation order, seed never masks an earlier failure), **FR-016** (all-or-nothing
  applies to every failure mode, not just insufficient-puzzles), **SC-007**
  (measurable per-failure-mode outcome), and two new Edge Cases entries (concurrent
  generation explicitly out of scope; minimum-threshold selection always
  distinct-satisfiable).

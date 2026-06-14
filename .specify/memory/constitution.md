<!--
SYNC IMPACT REPORT
==================
Version change: 1.1.0 → 1.1.1
Bump rationale: PATCH — added the append-only "Amendment History" section, a
durable in-file changelog. This is a non-semantic/organizational refinement: no
principle or governance rule was added, redefined, or removed. (A new section
that introduced normative guidance would be MINOR; this one only records
already-ratified history.)

For the full per-version history, see the Amendment History table near the end
of this file. Prior milestones: 1.0.0 initial ratification (five principles +
constraints + workflow + governance); 1.1.0 added Principle VI.

Modified principles: none.

Added principles: none.

Added sections:
  - Amendment History (append-only in-file changelog).

Removed sections: none

Templates requiring updates:
  ✅ .specify/templates/plan-template.md  — Constitution Check gate is generic
     ("[Gates determined based on constitution file]"); no edit required, it
     now resolves against these five principles.
  ✅ .specify/templates/spec-template.md  — already enforces independently
     testable user stories (Principle I) and MUST-style requirements; aligned.
  ✅ .specify/templates/tasks-template.md — already supports test-first
     ("write tests FIRST, ensure they FAIL"), integration tests, and
     observability tasks; aligned with Principles III & V.

Follow-up TODOs: none. Ratification date set to today (no prior adoption date
existed because the constitution was never previously filled in).
-->

# wheeldb Constitution

## Core Principles

### I. Library-First Architecture

Every feature MUST begin life as a standalone library module with a single,
clearly stated purpose. Each library MUST be:

- **Self-contained** — usable without the CLI and without live network access.
- **Independently testable** — exercised in isolation via the offline test suite
  (saved fixtures + mocked HTTP), never requiring the live site to pass.
- **Documented** — a module/function docstring stating purpose, inputs, and
  outputs.

Organizational-only modules (code grouped for no reason beyond grouping) are
prohibited. Rationale: the scraper's parser, storage, and HTTP layers are only
trustworthy if each can be verified on its own; this is why the suite already
runs fully offline.

### II. CLI Interface, No Spoilers

The program MUST be operable through a command-line interface using a text
in/out protocol: arguments and stdin in, results to stdout, errors and
diagnostics to stderr.

The CLI MUST NOT print Wheel of Fortune puzzle solutions during normal
operation. Puzzle text may be emitted **only** within tests. Normal runs report
progress, counts, and provenance — never the answers themselves. Rationale: the
tool exists to build a queryable database, not to reveal puzzles; the only place
a spoiler may surface is behind the test boundary, where a human has opted in.

### III. Test-First (NON-NEGOTIABLE)

Tests MUST be written before implementation code. The Red-Green-Refactor cycle
is strictly enforced: write the test, watch it fail, then implement until it
passes. Integration tests MUST be performed between specified features —
verifying that features work together, not merely in isolation — before a
feature is considered complete. Rationale: a scraper that parses live, drifting
third-party markup is only safe to change when behavior is pinned by tests
first.

### IV. Reuse Before Creation

Code MUST NOT be duplicated. Before adding a new method or function, existing
methods MUST be reviewed for suitability and reused or extended where they fit
the task. A new method is justified only when no existing one can reasonably
serve. Rationale: duplicated parsing/normalization logic drifts apart and rots;
a single source of truth per behavior keeps the codebase correct and small.

### V. Debuggable Tests

Tests MUST print ample debug output so that a failure is diagnosable from the
test log alone, without re-running under a debugger. Output MUST make the
relevant inputs, expected values, and actual values visible at the point of
failure. Rationale: failures in fixture-driven scraping tests are often about
*what the markup actually contained*; that context must be in the log.

### VI. Documented Methods

Every method MUST be immediately preceded by a docstring explaining what the
method is used for and describing each of its parameters. The docstring MUST
state the method's purpose and, for every parameter, its meaning (and return
value where one exists). A method without such a docstring is incomplete.
Rationale: parser, storage, and HTTP helpers are reused across the codebase
(Principle IV); a caller deciding whether an existing method fits a task must be
able to learn its contract from the docstring without reading the body.

## Additional Constraints

These operational constraints follow from the principles above and the project's
established behavior:

- **Stack**: Python with SQLite storage; the offline test suite is the source of
  truth for correctness.
- **Idempotent runs**: re-running the scraper MUST maintain (not duplicate) the
  database; rows are unique on their stable key and updated in place.
- **Respectful scraping**: requests honor a politeness delay and send a real
  browser `User-Agent`; the live site is never hammered in parallel.
- **Fixture-backed parsing**: parser logic is validated against captured
  representative HTML fixtures, which are updated together with parser changes.

## Development Workflow & Quality Gates

- **Constitution Check**: the `/speckit-plan` gate MUST verify a feature's plan
  against these five principles before design proceeds, and again after design.
- **Test-first gate**: tasks that add behavior MUST order their tests before
  their implementation (per Principle III); reviewers reject implementation
  submitted without preceding failing tests.
- **Reuse review**: code review MUST check that no new method duplicates an
  existing one (Principle IV) before approval.
- **Spoiler review**: code review MUST confirm no non-test code path prints
  puzzle solutions (Principle II).
- **Debug-output review**: new tests MUST demonstrate diagnostic output
  (Principle V).

## Governance

This constitution supersedes other development practices for this project. All
plans, specs, tasks, and reviews MUST verify compliance with the principles
above; any deviation MUST be justified in writing in the relevant plan's
Complexity Tracking section.

**Amendment procedure**: amendments are made by editing this file via
`/speckit-constitution`, which MUST also propagate changes to dependent
templates and record a Sync Impact Report.

**Versioning policy**: this constitution is versioned with semantic versioning —
MAJOR for backward-incompatible principle removals or redefinitions, MINOR for a
newly added principle or materially expanded guidance, PATCH for clarifications
and wording fixes.

**Compliance review**: compliance is checked at every plan gate and at code
review. Unjustified violations block the change.

## Amendment History

This section is append-only: each ratified version adds one row and existing
rows are never edited or removed. It is the durable in-file changelog and is not
overwritten by the Sync Impact Report (which reflects only the latest change).

| Version | Date | Type | Summary |
| ------- | ---- | ---- | ------- |
| 1.0.0 | 2026-06-14 | MAJOR | Initial ratification: five principles (Library-First, CLI/No-Spoilers, Test-First, Reuse Before Creation, Debuggable Tests), Additional Constraints, Development Workflow & Quality Gates, and Governance. |
| 1.1.0 | 2026-06-14 | MINOR | Added Principle VI (Documented Methods): every method preceded by a docstring covering its use and each parameter. |
| 1.1.1 | 2026-06-14 | PATCH | Added this append-only Amendment History section (durable in-file changelog). No normative change. |

**Version**: 1.1.1 | **Ratified**: 2026-06-14 | **Last Amended**: 2026-06-14

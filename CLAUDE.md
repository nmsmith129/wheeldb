# Test-First is NON-NEGOTIABLE (Constitution Principle III)

For ANY behavioral change in this project, in EVERY conversation:

1. Write (or extend) the test FIRST.
2. Run `py -m pytest` and observe it FAIL for the right reason (the red phase).
3. Only then write the implementation, until the test passes (green).
4. Work one unit of behavior at a time. Do NOT batch source code ahead of tests.

This rule overrides momentum, "obvious" implementations, and time pressure. If
you find yourself about to write source before a failing test exists, STOP.
A `PreToolUse(Write)` hook (`.claude/hooks/test_first_guard.py`) enforces this by
running the tests that reference a module under `src/` and blocking the Write
unless they are currently FAILING (red) — do not work around it; write the
failing test first. (The hook is project-agnostic: it gates any `src/<pkg>/`
module, which in this repo is `src/wheeldb/`.) Full governance: `.specify/memory/constitution.md`.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/005-csv-output-format/plan.md
<!-- SPECKIT END -->

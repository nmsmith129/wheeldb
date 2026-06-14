#!/usr/bin/env python
"""PreToolUse(Write) guard enforcing test-first (Constitution Principle III).

Project-agnostic: blocks writing any source module under a ``src/`` package
unless a test that references it is currently FAILING. Because PreToolUse runs
before the write, the referencing tests are evaluated against the on-disk state
*without* the module being written -- so a red result means the write is the
implementation that turns it green (correct TDD), while a green result means
there is no failing test to justify writing the implementation.

Conventions assumed (standard Python layout): source lives under ``src/<pkg>/``
and tests under ``<repo>/tests/``. Scope is ``Write`` only -- ``Edit`` is
unguarded, so refactors / bug-fix rewrites of existing files are never blocked.
Test files (``test_*.py`` / ``*_test.py``, or anything under a ``tests`` dir)
are never gated, even if they live under ``src/``.

Exit codes: 0 = allow, 2 = block (stderr is shown to the agent).
"""

import json
import subprocess
import sys
from pathlib import Path

# .claude/hooks/this.py -> parents[2] == repo root (cwd-independent).
REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "tests"

# Files with no behavior of their own to test first.
EXEMPT = {"__init__.py", "__main__.py"}

# pytest exit codes that mean "red" (a real failing/erroring test exists):
#   1 = tests failed; 2 = collection/usage error (e.g. the module import fails).
RED_EXIT_CODES = {1, 2}


def _block(message: str) -> int:
    sys.stderr.write(message)
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # unparseable input: don't get in the way

    raw_path = payload.get("tool_input", {}).get("file_path", "")
    if not raw_path:
        return 0

    norm = raw_path.replace("\\", "/")
    parts = norm.split("/")

    # Gate only .py files that live under a "src/" package...
    if not norm.endswith(".py") or "src" not in parts:
        return 0
    name = parts[-1]
    # ...but never gate test files, even if nested under src/.
    if (
        name in EXEMPT
        or name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in parts
    ):
        return 0

    idx = len(parts) - 1 - parts[::-1].index("src")  # last "src" segment
    if idx >= len(parts) - 1:
        return 0  # "src" with nothing after it: not a module path
    display = "/".join(parts[idx:])  # e.g. src/wheeldb/parser.py
    module = name[:-3]  # strip ".py"

    # 1. A test must reference the module at all (and tells us what to run).
    referencing = []
    if TESTS_DIR.is_dir():
        for test_file in sorted(TESTS_DIR.rglob("*.py")):
            try:
                if module in test_file.read_text(encoding="utf-8", errors="ignore"):
                    referencing.append(test_file)
            except OSError:
                continue

    if not referencing:
        return _block(
            "BLOCKED by test-first guard (Constitution Principle III, NON-NEGOTIABLE).\n"
            f"No test under tests/ references the module '{module}'.\n"
            f"Write the failing test for {display} FIRST, then create the module.\n"
            "If this is a deliberate exception, stop and ask the user to confirm."
        )

    # 2. Those tests must currently FAIL (red) -- run them against the pre-write
    #    state. -x stops at the first failure so the common red case is fast.
    rel = [str(p.relative_to(REPO_ROOT)).replace("\\", "/") for p in referencing]
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", *rel],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _block(
            "BLOCKED by test-first guard: could not run the referencing tests to "
            f"confirm they fail first ({exc}).\n"
            "Run `py -m pytest` on the relevant tests manually, confirm red, then retry."
        )

    if proc.returncode in RED_EXIT_CODES:
        return 0  # red confirmed: this write is the implementation that turns it green

    if proc.returncode == 0:
        return _block(
            "BLOCKED by test-first guard (Constitution Principle III, NON-NEGOTIABLE).\n"
            f"The tests referencing '{module}' already PASS without this write:\n"
            f"  {', '.join(rel)}\n"
            "You must observe a FAILING test before writing the implementation.\n"
            "Add or extend a test that fails for the right reason first. (To change an "
            "existing module, use Edit -- it is not gated.)"
        )

    # Any other exit code (e.g. 5 = no tests collected): don't claim red.
    return _block(
        "BLOCKED by test-first guard: running the referencing tests did not produce a "
        f"clear failing result (pytest exit {proc.returncode}).\n"
        f"  files: {', '.join(rel)}\n"
        "Ensure a test that fails for the right reason exists, confirm it red with "
        "`py -m pytest`, then retry."
    )


if __name__ == "__main__":
    sys.exit(main())

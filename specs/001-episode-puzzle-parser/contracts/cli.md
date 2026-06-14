# Contract: CLI Interface (spoiler-free)

Per Principle II: arguments + stdin in, results to stdout, errors/diagnostics to
stderr, and **no puzzle solutions printed during normal operation**.

## Invocation

```text
wheeldb episode <EPISODE_NUMBER>
```

(Equivalently `python -m wheeldb episode <EPISODE_NUMBER>`.)

| Argument | Required | Meaning |
|----------|----------|---------|
| `<EPISODE_NUMBER>` | yes | Global episode number to extract (positive integer). |

## stdout (success)

A spoiler-free report — counts and provenance only, never solutions:

```text
Episode 8011 (Season 42): 3 puzzles found
  Rounds: T1, R2, BR
  Source: https://buyavowel.boards.net/page/compendium42
```

- Reports puzzle **count**, the **season** the episode was found in, the
  **round codes** present, and the **source URL** (provenance).
- MUST NOT print any `solution`, `category` value paired with its answer, or any
  other puzzle text that reveals an answer.

## stdout (episode not found)

```text
Episode 99999: 0 puzzles found
```

Exit code `0` — "not found" is a valid result, not an error (FR-010).

## stderr + exit codes

| Condition | stderr | Exit code |
|-----------|--------|-----------|
| Success (incl. 0 found) | progress/diagnostics only | `0` |
| Retrieval failure (e.g. HTTP 403, network) | `error: could not retrieve season data: <detail>` | non-zero |
| Bad usage (missing/invalid episode number) | usage message | non-zero |

## Notes

- Progress/diagnostic lines (e.g. "searching season 41…") go to **stderr**, so
  stdout stays a clean machine-readable report.
- The full puzzle objects (with solutions) are available only via the library
  API and the test-only print option — never via CLI stdout (FR-013).

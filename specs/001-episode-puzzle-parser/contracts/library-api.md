# Contract: Public Library API

The deliverable is a Python library (Principle I). This is its public surface.
Signatures are contracts; bodies are implemented in the implementation phase.

## `Puzzle`

A value object exposing the six required attributes plus derivations. See
[data-model.md](../data-model.md) for full field semantics.

```python
@dataclass(frozen=True)
class Puzzle:
    solution: str        # normalized answer text (quotes stripped)
    category: str        # trimmed category
    date: str            # ISO YYYY-MM-DD when parseable, else raw source text
    season: int          # season number the episode belongs to
    episode: int         # global episode number
    round: str           # clean raw round code, e.g. "T1" / "R2" / "BR"
    flags: tuple = ()    # ((column, symbol), ...) annotations seen; default empty

    @property
    def round_name(self) -> str: ...   # "R2" -> "Round 2"
    @property
    def puzzle_type(self) -> str: ...  # "R*" -> "Round", "T*" -> "Toss-Up", "BR" -> "Bonus Round"
```

**Contract guarantees**

- `solution` has no surrounding quotes; `round` has no trailing `*`/`^`; `date`
  has no trailing `*`.
- Equality/uniqueness is keyed on `(season, episode, round, solution)`.

## `extract_episode`

```python
def extract_episode(episode_number: int, *, fetcher: Fetcher | None = None) -> list[Puzzle]:
    """Return every puzzle that aired in the given episode.

    Searches compendium season pages, matches the EP# column, and returns the
    matching rows normalized to Puzzle objects, ordered by round as aired.

    Parameters:
        episode_number: the show's global episode number (EP# without '#').
        fetcher: optional retrieval strategy; defaults to the live browser-UA
            fetcher. Tests inject a fixture-backed fetcher (offline).

    Returns:
        A list of Puzzle objects (possibly empty if the episode is in no season).

    Raises:
        RetrievalError: a season page could not be retrieved (e.g. HTTP 403 /
            network failure) — distinct from an empty result.
    """
```

**Contract guarantees**

- Returns `[]` (no error) when `episode_number` exists in no season (FR-010).
- Raises `RetrievalError` on retrieval failure, never confusing it with "not
  found" (FR-011).
- Every returned puzzle has `episode == episode_number` and the `season` of the
  page it was found on (FR-008).
- Does NOT print puzzle solutions (Principle II / FR-013).

## `Fetcher` (injection seam for offline tests)

```python
class Fetcher(Protocol):
    def get_season_html(self, season_number: int) -> str:
        """Return the raw HTML of compendium page {season_number}.

        Parameters:
            season_number: 1-based season page number to retrieve.
        Returns:
            Raw HTML text of the season page.
        Raises:
            RetrievalError: the page could not be retrieved.
        """
```

- Default implementation: live HTTP with browser `User-Agent` + politeness delay.
- Test implementation: reads from `tests/fixtures/compendium{N}.html`.

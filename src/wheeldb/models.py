"""The Puzzle value object.

A ``Puzzle`` is one Wheel of Fortune puzzle from one round of one episode. It
exposes the six attributes the feature requires (solution, category, date,
season, episode, round) plus convenience derivations and preserved annotation
flags. See specs/001-episode-puzzle-parser/data-model.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Puzzle:
    """An immutable puzzle record produced by parsing a season page.

    Uniqueness is keyed on (season, episode, round, solution); ``flags`` is
    excluded from equality because it is derived from the same source row.
    """

    solution: str
    category: str
    date: str
    season: int
    episode: int
    round: str
    flags: tuple = field(default=(), compare=False)

    @property
    def round_name(self) -> str:
        """Return a human-readable expansion of the round code.

        Returns:
            ``Bonus Round`` for ``BR``; ``Toss-Up N`` for ``TN``; ``Round N`` for
            ``RN``; otherwise the raw code unchanged.
        """
        code = self.round
        if code == "BR":
            return "Bonus Round"
        if code[:1] == "T":
            return f"Toss-Up {code[1:]}"
        if code[:1] == "R":
            return f"Round {code[1:]}"
        return code

    @property
    def puzzle_type(self) -> str:
        """Return the coarse puzzle type derived from the round code.

        Returns:
            ``Toss-Up`` for ``T*``, ``Round`` for ``R*``, ``Bonus Round`` for
            ``BR``; otherwise ``Unknown``.
        """
        if self.round == "BR":
            return "Bonus Round"
        if self.round[:1] == "T":
            return "Toss-Up"
        if self.round[:1] == "R":
            return "Round"
        return "Unknown"

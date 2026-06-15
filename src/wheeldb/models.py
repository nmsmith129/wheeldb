"""The Puzzle value object.

A ``Puzzle`` is one Wheel of Fortune puzzle from one round of one episode. It
exposes the six attributes the feature requires (solution, category, date,
season, episode, round) plus convenience derivations and preserved annotation
flags. See specs/001-episode-puzzle-parser/data-model.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from wheeldb.errors import ParseError, PuzzleParseError

__all__ = ["Puzzle", "PuzzleParseError", "round_from_type_and_number"]


def round_from_type_and_number(puzzle_type: str, puzzle_number: int) -> str:
    """Reconstruct a round code from its derived puzzle type and number.

    The exact inverse of :attr:`Puzzle.puzzle_type` / :attr:`Puzzle.puzzle_number`,
    co-located with them so the round <-> type/number mapping has a single source
    of truth (Constitution Principle IV). Used by the CSV store, whose rows carry
    ``puzzle_type``/``puzzle_number`` columns but no ``round`` column, to recover
    the stable identity key ``(season, episode, round)``.

    Parameters:
        puzzle_type: the coarse type — ``"Bonus Round"``, ``"Toss-Up"``, or
            ``"Round"``.
        puzzle_number: the numeric suffix (``0`` for the bonus round).
    Returns:
        The round code: ``"BR"`` for the bonus round, ``"T<N>"`` for a toss-up,
        ``"R<N>"`` for a numbered round.
    Raises:
        PuzzleParseError: the type/number pair is not a recognized combination, so
            no round code can be reconstructed (a data error, FR-004).
    """
    if puzzle_type == "Bonus Round":
        return "BR"
    if puzzle_type == "Toss-Up":
        return f"T{puzzle_number}"
    if puzzle_type == "Round":
        return f"R{puzzle_number}"
    raise PuzzleParseError(
        f"cannot reconstruct round code from puzzle_type {puzzle_type!r} and "
        f"puzzle_number {puzzle_number!r}"
    )

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
    
    @property
    def puzzle_number(self) -> int:
        """Return the coarse puzzle number derived from the round code.

        Returns:
            ``0`` for the bonus round (``BR``); otherwise the numeric suffix of a
            toss-up (``T*``) or numbered round (``R*``).
        Raises:
            PuzzleParseError: the round code is not a recognized ``BR``/``T*``/``R*``
                form, so no puzzle number can be derived (a data error, FR-010).
        """
        if self.round == "BR":
            return 0
        if self.round[:1] == "T" or self.round[:1] == "R":
            return int(self.round[1:])
        raise PuzzleParseError(
            f"cannot derive puzzle number for unrecognized round code {self.round!r} "
            f"(season {self.season}, episode {self.episode})"
        )
        
    def puzzle_id(self) -> str:
        """Return a unique identifier for the puzzle."""
        try:
            return f"{self.season}-{self.episode}-{self.round}"
        except Exception as e:
            raise ParseError(f"Error generating puzzle ID: {e}")
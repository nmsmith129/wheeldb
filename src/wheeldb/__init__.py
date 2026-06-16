"""wheeldb: extract Wheel of Fortune puzzles for an episode.

Public surface: the ``Puzzle`` value object and ``extract_episode`` retrieval
function, plus the typed errors and the ``Fetcher`` seam for offline use.
"""

from wheeldb.csv_storage import CsvPuzzleStore
from wheeldb.episodes import extract_episode
from wheeldb.errors import (
    DatabaseError,
    GameError,
    ParseError,
    RetrievalError,
    WheelDBError,
)
from wheeldb.fetch import Fetcher, HttpFetcher, season_url
from wheeldb.gamegen import generate_game, next_game_number
from wheeldb.ingest import IngestSummary, ingest_seasons, parse_season_arg
from wheeldb.models import Puzzle
from wheeldb.pptx_inject import inject_puzzles
from wheeldb.storage import PuzzleStore

__all__ = [
    "Puzzle",
    "extract_episode",
    "Fetcher",
    "HttpFetcher",
    "season_url",
    "WheelDBError",
    "RetrievalError",
    "ParseError",
    "DatabaseError",
    "GameError",
    "PuzzleStore",
    "CsvPuzzleStore",
    "ingest_seasons",
    "parse_season_arg",
    "IngestSummary",
    "generate_game",
    "next_game_number",
    "inject_puzzles",
]

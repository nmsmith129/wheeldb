"""wheeldb: extract Wheel of Fortune puzzles for an episode.

Public surface: the ``Puzzle`` value object and ``extract_episode`` retrieval
function, plus the typed errors and the ``Fetcher`` seam for offline use.
"""

from wheeldb.episodes import extract_episode
from wheeldb.errors import DatabaseError, ParseError, RetrievalError, WheelDBError
from wheeldb.fetch import Fetcher, HttpFetcher, season_url
from wheeldb.ingest import IngestSummary, ingest_seasons, parse_season_arg
from wheeldb.models import Puzzle
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
    "PuzzleStore",
    "ingest_seasons",
    "parse_season_arg",
    "IngestSummary",
]

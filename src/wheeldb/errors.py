"""Typed errors for the wheeldb library.

These let callers distinguish a *retrieval* failure (the source could not be
fetched) from a *parse* failure (a fetched page did not contain the expected
puzzle table), and both from an ordinary empty result (FR-010 vs FR-011).
"""


class WheelDBError(Exception):
    """Base class for all wheeldb errors."""


class RetrievalError(WheelDBError):
    """A season page could not be retrieved (e.g. HTTP 403, network failure).

    Distinct from "episode not found": a clean fetch that simply contains no
    matching episode yields an empty result, not this error.
    """


class ParseError(WheelDBError):
    """A fetched page did not contain a recognizable puzzle table."""


class DatabaseError(WheelDBError):
    """The SQLite puzzle database could not be opened or written.

    Raised by the storage layer for an unopenable path, a schema-creation
    failure, or any underlying ``sqlite3`` error during a read/write — so callers
    can distinguish a persistence failure from a retrieval or parse failure.
    """


class GameError(WheelDBError):
    """A playable game file could not be generated.

    Raised by game generation (``gamegen``) and package injection
    (``pptx_inject``) for the feature-006 failure modes: the season is absent or
    holds too few puzzles of a type, no ``wof[N].pptm`` number is available, the
    template is missing/unreadable, or a puzzle slot's anchor cannot be located.
    A direct ``WheelDBError`` subclass so the CLI maps it to a clear, spoiler-free
    stderr message and exit 2 (FR-010/FR-014). Messages name only types, counts,
    seasons, and paths — never a solution or category (Decision 6/7).
    """


class PuzzleParseError(WheelDBError):
    """A puzzle's round code is not recognized, so a derived value cannot be computed.

    Distinct from :class:`ParseError` (which is about the page-level table): this
    is a per-row data error. It is a direct ``WheelDBError`` subclass — not a
    ``ParseError`` — so a caller skipping ``ParseError`` does not accidentally
    swallow it; ingestion treats it as a halting data error (FR-010).
    """

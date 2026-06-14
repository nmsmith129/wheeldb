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

#!/usr/bin/env python3
"""wheeldb - scrape the Buy A Vowel Boards Wheel of Fortune Puzzle Compendium
into a local SQLite database.

The compendium (https://buyavowel.boards.net/page/compendiumindex) is a set of
per-season pages listing every episode's puzzles. This single script fetches the
index, follows each season link, parses out the individual puzzles, and stores
them in SQLite so they can be queried/sorted by season, episode, puzzle type,
category, air date, and round name.

Re-running the script is safe: writes are upserts keyed on
(season, episode, round_name, solution), so an existing database is *maintained*
(refreshed and extended) rather than duplicated.

Run `python wheeldb.py --help` for usage.
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

# The compendium index lists every season; everything else is discovered from it.
INDEX_URL = "https://buyavowel.boards.net/page/compendiumindex"

# buyavowel.boards.net returns HTTP 403 to non-browser user agents, so we must
# present a real browser User-Agent on every request or the scrape fails wholesale.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Politeness defaults: wait between requests and cap how long any single request
# may block, so a slow page can't hang the whole run.
DEFAULT_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30

# Retry schedule for transient network/server failures. Mirrors the project's
# documented push-retry pattern (exponential backoff: 2s, 4s, 8s, 16s).
RETRY_BACKOFFS = (2, 4, 8, 16)

# Status codes worth retrying: transient server-side errors. A 403 here is *not*
# transient (it means UA/egress blocking), so it is surfaced immediately instead.
RETRYABLE_STATUS = {500, 502, 503, 504, 429}

log = logging.getLogger("wheeldb")


class EgressBlockedError(RuntimeError):
    """Raised when a request is refused in a way the user must fix in config.

    Distinguishes a 403 / egress-allowlist rejection (an environment/configuration
    problem) from ordinary transient failures, so the CLI can print actionable
    guidance instead of burning retries on something that will never succeed.
    """


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
def make_session(user_agent: str = DEFAULT_USER_AGENT) -> requests.Session:
    """Build a configured ``requests.Session`` for all scraping calls.

    Centralising session creation means every request carries the browser
    User-Agent required to get past the site's 403 filter, and connection
    pooling is reused across the many per-season fetches.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def _cache_path(cache_dir: Path, url: str) -> Path:
    """Map a URL to a stable on-disk cache filename.

    A deterministic, filesystem-safe name lets a second run (or the parser tests)
    reuse a previously downloaded page instead of hitting the network again.
    """
    # Use the final path segment plus a hash-free slug so files are human-readable
    # when inspecting the cache directory by hand.
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("//", 1)[-1])
    return cache_dir / f"{slug}.html"


def fetch(
    session: requests.Session,
    url: str,
    *,
    delay: float = DEFAULT_DELAY_SECONDS,
    cache_dir: Optional[Path] = None,
    dump_html: bool = False,
) -> str:
    """Fetch ``url`` and return its HTML, with caching, politeness, and retries.

    This is the single choke point for network access so the politeness delay,
    retry/backoff, optional on-disk cache, and 403/egress detection are applied
    uniformly to every page the scraper touches.
    """
    cache_file = _cache_path(cache_dir, url) if cache_dir else None

    # Serve from cache when available: avoids re-downloading during development
    # and makes repeated runs cheap and gentle on the source site.
    if cache_file and cache_file.exists() and not dump_html:
        log.debug("cache hit %s", cache_file)
        return cache_file.read_text(encoding="utf-8")

    last_error: Optional[Exception] = None
    # One initial attempt plus one per backoff interval.
    for attempt in range(len(RETRY_BACKOFFS) + 1):
        # Be polite: pause before every network attempt, including retries.
        time.sleep(delay)
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            # Connection-level failures (DNS, reset, timeout) are transient.
            last_error = exc
            log.warning("request error for %s: %s", url, exc)
        else:
            if resp.status_code == 403:
                # Not retryable: the request is being refused, typically because
                # the host is missing from the egress allowlist or the UA is blocked.
                raise EgressBlockedError(
                    f"403 Forbidden for {url}. The host may be missing from the "
                    "environment's network egress allowlist, or the site is "
                    "blocking the User-Agent. Add 'buyavowel.boards.net' to the "
                    "Custom allowed domains and start a fresh session."
                )
            if resp.status_code in RETRYABLE_STATUS:
                last_error = RuntimeError(f"HTTP {resp.status_code} for {url}")
                log.warning("transient HTTP %s for %s", resp.status_code, url)
            else:
                resp.raise_for_status()  # Surface any other 4xx as a hard error.
                html = resp.text
                if cache_file:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(html, encoding="utf-8")
                return html

        # Back off before the next attempt, if any remain.
        if attempt < len(RETRY_BACKOFFS):
            wait = RETRY_BACKOFFS[attempt]
            log.info("retrying %s in %ss (attempt %s)", url, wait, attempt + 1)
            time.sleep(wait)

    raise RuntimeError(f"failed to fetch {url} after retries: {last_error}")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def derive_puzzle_type(round_name: str) -> str:
    """Reduce a specific round label to its general puzzle type.

    The user wants both the precise round (e.g. ``"Toss-Up 1"``) and a coarser
    "puzzle type" (e.g. ``"Toss-Up"``) to group/sort by. The type is the round
    name with any trailing instance marker removed: a number (``"Round 2"`` ->
    ``"Round"``), a single letter (``"Triple Toss-Up A"`` -> ``"Triple Toss-Up"``),
    or nothing (``"Bonus Round"`` stays ``"Bonus Round"``).
    """
    name = (round_name or "").strip()
    # Strip a trailing " 2", " #2", or " A" style instance marker. Anchored to the
    # end so multi-word types like "Triple Toss-Up" keep their internal words.
    stripped = re.sub(r"\s*#?\d+$", "", name)  # numeric suffix: "Round 2" -> "Round"
    stripped = re.sub(r"\s+[A-Z]$", "", stripped)  # letter suffix: "... A" -> "..."
    return stripped.strip() or name


def normalize_date(raw: str) -> Optional[str]:
    """Normalise a human-readable air date to ISO ``YYYY-MM-DD``.

    Air dates appear in mixed formats on the site; storing a canonical ISO string
    makes chronological sorting and range queries reliable. Returns ``None`` for
    empty input and the cleaned original string if no known format matches, so an
    unparseable date is preserved rather than silently dropped.
    """
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    # Try the formats the compendium is known to use, most specific first.
    formats = (
        "%B %d, %Y",   # September 19, 2024
        "%b %d, %Y",   # Sep 19, 2024
        "%m/%d/%Y",    # 09/19/2024
        "%m/%d/%y",    # 09/19/24
        "%Y-%m-%d",    # already ISO
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Unknown format: keep the original text so no information is lost.
    log.debug("unrecognised date format: %r", text)
    return text


def _clean(text: str) -> str:
    """Collapse whitespace in scraped text.

    HTML often introduces stray newlines/tabs and non-breaking spaces; normalising
    them keeps stored solutions and categories clean and comparable for upserts.
    """
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def parse_index(html: str) -> list[tuple[int, str]]:
    """Extract ``(season_number, season_url)`` pairs from the compendium index.

    The index is the entry point that tells the scraper which season pages exist,
    so the rest of the run can iterate seasons without hard-coding their URLs.
    Season links are recognised by an explicit ``Season N`` label on the link.
    """
    soup = BeautifulSoup(html, "lxml")
    seasons: dict[int, str] = {}
    for link in soup.find_all("a", href=True):
        label = _clean(link.get_text())
        match = re.search(r"Season\s+(\d+)", label, flags=re.IGNORECASE)
        if not match:
            continue
        season = int(match.group(1))
        url = _absolute_url(link["href"])
        # First occurrence wins; the index can repeat a season in nav/footers.
        seasons.setdefault(season, url)
    return sorted(seasons.items())


def _absolute_url(href: str) -> str:
    """Resolve a possibly-relative compendium href to an absolute URL.

    Links on the index are often root-relative (``/page/...``); making them
    absolute lets ``fetch`` request them directly.
    """
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return "https://buyavowel.boards.net" + (href if href.startswith("/") else "/" + href)


def parse_season(html: str, season: int, source_url: str) -> list[dict]:
    """Parse one season page into a list of puzzle records.

    This is the core extraction step: it walks the season page's puzzle rows and
    produces normalised dicts ready for ``upsert_puzzles``. Rows are read from
    tables, carrying the current episode/air-date context forward across the
    puzzle rows that belong to it.

    NOTE: the exact column order/markup is finalised against real saved pages
    (see the plan's "Build order"); the logic below targets the compendium's
    table layout of [round, category, solution] rows grouped under an episode
    header that carries the episode number and air date.
    """
    soup = BeautifulSoup(html, "lxml")
    puzzles: list[dict] = []
    current_episode: Optional[str] = None
    current_air_date: Optional[str] = None

    for row in soup.find_all("tr"):
        cells = [_clean(td.get_text()) for td in row.find_all(["td", "th"])]
        cells = [c for c in cells if c != ""]
        if not cells:
            continue

        # An episode header row introduces the episode number and air date and
        # sets the context for the puzzle rows that follow it.
        episode, air_date = _match_episode_header(cells)
        if episode is not None:
            current_episode = episode
            current_air_date = air_date
            continue

        # A puzzle row has a recognisable round label in its first column.
        round_name = _match_round(cells[0])
        if round_name is None:
            continue
        # Layout is [round, category, solution]; tolerate a missing category.
        category = cells[1] if len(cells) >= 3 else None
        solution = cells[-1]
        if not solution:
            continue

        puzzles.append(
            {
                "season": season,
                "episode": current_episode,
                "air_date": current_air_date,
                "round_name": round_name,
                "puzzle_type": derive_puzzle_type(round_name),
                "category": category,
                "solution": solution,
                "source_url": source_url,
            }
        )
    return puzzles


# Recognised round labels, used to tell puzzle rows apart from layout/noise rows.
_ROUND_PATTERN = re.compile(
    r"^(?:"
    r"Toss[- ]?Up(?:\s*#?\d+)?|"
    r"Triple\s+Toss[- ]?Up(?:\s+[A-Z])?|"
    r"Round\s*#?\d+|"
    r"Bonus(?:\s+Round)?|"
    r"Prize\s+Puzzle|"
    r"Mystery(?:\s+Round)?(?:\s*#?\d+)?|"
    r"Express(?:\s+Round)?|"
    r"Speed[- ]?Up(?:\s+Round)?|"
    r"Final\s+Spin"
    r")",
    flags=re.IGNORECASE,
)


def _match_round(text: str) -> Optional[str]:
    """Return the normalised round label if ``text`` names a round, else ``None``.

    Used to decide whether a table row is an actual puzzle (and to capture its
    round name) versus unrelated layout text, keeping noise out of the database.
    """
    if _ROUND_PATTERN.match(text):
        return text
    return None


# Episode headers look like "Episode 1234 - September 19, 2024" (separators vary).
# The episode token must start with a digit so unrelated text that merely contains
# a keyword (e.g. a "Show Biz" category) isn't misread as an episode header.
_EPISODE_PATTERN = re.compile(
    r"\b(?:Episode|Show|Ep\.?)\s*#?\s*(\d[\w.-]*)"
    r"(?:\s*[-–—:]\s*(.+))?$",
    flags=re.IGNORECASE,
)


def _match_episode_header(cells: list[str]) -> tuple[Optional[str], Optional[str]]:
    """Detect an episode-header row and return ``(episode, air_date)``.

    Episode headers establish which episode (and air date) the following puzzle
    rows belong to; recognising them is what lets a flat row stream be grouped
    back into episodes. Returns ``(None, None)`` when the row is not a header.
    """
    joined = " ".join(cells)
    match = _EPISODE_PATTERN.search(joined)
    if not match:
        return None, None
    episode = match.group(1)
    air_date = normalize_date(match.group(2)) if match.group(2) else None
    return episode, air_date


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS puzzles (
    id          INTEGER PRIMARY KEY,
    season      INTEGER NOT NULL,
    episode     TEXT,
    air_date    TEXT,
    round_name  TEXT,
    puzzle_type TEXT,
    category    TEXT,
    solution    TEXT NOT NULL,
    source_url  TEXT,
    scraped_at  TEXT,
    UNIQUE(season, episode, round_name, solution)
);
CREATE INDEX IF NOT EXISTS idx_season   ON puzzles(season);
CREATE INDEX IF NOT EXISTS idx_episode  ON puzzles(season, episode);
CREATE INDEX IF NOT EXISTS idx_type     ON puzzles(puzzle_type);
CREATE INDEX IF NOT EXISTS idx_category ON puzzles(category);
CREATE INDEX IF NOT EXISTS idx_airdate  ON puzzles(air_date);
CREATE INDEX IF NOT EXISTS idx_round    ON puzzles(round_name);
"""


def init_db(path: str) -> sqlite3.Connection:
    """Open the SQLite database at ``path`` and ensure the schema exists.

    Idempotent (``CREATE ... IF NOT EXISTS``) so the same call works whether the
    database is brand new or being maintained, which is the whole point of a
    re-runnable build/update script.
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_puzzles(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    """Insert or refresh puzzle rows, returning how many were written.

    Uses ``ON CONFLICT`` against the natural key (season, episode, round_name,
    solution) so re-scraping never creates duplicates: unchanged puzzles just get
    a refreshed ``scraped_at``, and changed metadata (category/air date) is
    updated in place. This is what makes the database *maintainable* over time.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO puzzles
                (season, episode, air_date, round_name, puzzle_type,
                 category, solution, source_url, scraped_at)
            VALUES
                (:season, :episode, :air_date, :round_name, :puzzle_type,
                 :category, :solution, :source_url, :scraped_at)
            ON CONFLICT(season, episode, round_name, solution) DO UPDATE SET
                air_date    = excluded.air_date,
                puzzle_type = excluded.puzzle_type,
                category    = excluded.category,
                source_url  = excluded.source_url,
                scraped_at  = excluded.scraped_at
            """,
            {**row, "scraped_at": now},
        )
        written += 1
    conn.commit()
    return written


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def select_seasons(available: list[tuple[int, str]], spec: str) -> list[tuple[int, str]]:
    """Filter the discovered seasons down to the user's ``--seasons`` selection.

    Lets the same scrape pipeline serve a full build (``all``), a single season
    (``42``), or a contiguous range (``30-42``) without duplicating orchestration
    logic for each case.
    """
    if spec == "all":
        return available
    if "-" in spec:
        low, high = (int(p) for p in spec.split("-", 1))
        return [(s, u) for s, u in available if low <= s <= high]
    wanted = int(spec)
    return [(s, u) for s, u in available if s == wanted]


def scrape(
    conn: sqlite3.Connection,
    session: requests.Session,
    *,
    seasons: str = "all",
    update: bool = False,
    delay: float = DEFAULT_DELAY_SECONDS,
    cache_dir: Optional[Path] = None,
    dump_html: bool = False,
) -> int:
    """Run the full fetch -> parse -> upsert pipeline and return puzzles written.

    This ties the layers together: discover seasons from the index, narrow them
    per the CLI flags, then parse and persist each season page. Keeping it as one
    function (separate from ``main``) makes the whole pipeline testable end-to-end
    with a mocked session.
    """
    index_html = fetch(session, INDEX_URL, delay=delay, cache_dir=cache_dir, dump_html=dump_html)
    available = parse_index(index_html)
    log.info("discovered %s seasons in the index", len(available))

    # `--update` is a cheap maintenance run: only refresh the latest season.
    if update and available:
        available = [max(available, key=lambda pair: pair[0])]
        log.info("update mode: scraping latest season %s only", available[0][0])
    else:
        available = select_seasons(available, seasons)

    total = 0
    for season, url in available:
        html = fetch(session, url, delay=delay, cache_dir=cache_dir, dump_html=dump_html)
        puzzles = parse_season(html, season, url)
        written = upsert_puzzles(conn, puzzles)
        total += written
        log.info("season %s: %s puzzles", season, written)
    return total


def build_arg_parser() -> argparse.ArgumentParser:
    """Define the command-line interface.

    Isolated from ``main`` so the argument schema can be exercised directly in
    tests and reused if the script is ever imported.
    """
    parser = argparse.ArgumentParser(
        description="Scrape the Buy A Vowel Boards WOF Puzzle Compendium into SQLite."
    )
    parser.add_argument("--db", default="puzzles.db", help="SQLite database path.")
    parser.add_argument(
        "--seasons",
        default="all",
        help="Seasons to scrape: 'all', a number (e.g. 42), or a range (e.g. 30-42).",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Scrape only the latest season (cheap maintenance run).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Seconds to wait before each request (politeness).",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for the on-disk HTML cache (omit to disable caching).",
    )
    parser.add_argument(
        "--dump-html",
        action="store_true",
        help="Save fetched pages to the cache dir for parser inspection (bypasses cache reads).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point: parse args, run the scrape, report results.

    Wraps the pipeline with user-facing logging and turns the egress/403 case
    into a clear, actionable message and a non-zero exit code instead of a stack
    trace, since that failure is a configuration issue the user must resolve.
    """
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    # --dump-html only makes sense with somewhere to write; default the location.
    if args.dump_html and cache_dir is None:
        cache_dir = Path("html_cache")

    conn = init_db(args.db)
    session = make_session()
    try:
        total = scrape(
            conn,
            session,
            seasons=args.seasons,
            update=args.update,
            delay=args.delay,
            cache_dir=cache_dir,
            dump_html=args.dump_html,
        )
    except EgressBlockedError as exc:
        log.error("%s", exc)
        return 2
    finally:
        conn.close()

    log.info("done: %s puzzles written to %s", total, args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())

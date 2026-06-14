# Feature Specification: Episode Puzzle Parser

**Feature Branch**: `001-episode-puzzle-parser`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "A Python parser that extracts all puzzles from an episode of Wheel of Fortune (specified by episode number) and returns them. There should be a class for puzzles containing attributes for puzzle solution, category, date, season number, episode number, and round. Make sure to have an option in testing to print out the puzzles. All puzzle solutions are to be taken from buyavowel.boards.net. The information in FORMAT.md is to be consulted whenever possible."

## Clarifications

### Session 2026-06-14

- Q: How should the parser determine which season contains the requested episode number? → A: The parser searches compendium season pages and returns rows whose `EP#` matches the requested episode; it owns the lookup end-to-end (no caller-supplied season required).
- Q: What should the `round` attribute hold? → A: The clean raw round code (`T1`/`R2`/`BR`), with annotation symbols stripped.
- Q: What form should the `date` attribute take? → A: ISO `YYYY-MM-DD` string when the source date is parseable; the original raw text is retained when it is not.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve all puzzles for an episode (Priority: P1)

A user (a developer or data-collection process) provides a Wheel of Fortune
episode number and gets back every puzzle that aired in that episode, each with
its solution, category, air date, season number, episode number, and round —
sourced from the Buy A Vowel Boards puzzle compendium.

**Why this priority**: This is the entire purpose of the feature. Without the
ability to turn an episode number into the set of puzzles for that episode,
nothing else has value. It is the minimum viable slice.

**Independent Test**: Provide a known episode number (e.g. one captured in a
saved HTML fixture such as S42 episode #8011) and confirm the parser returns the
correct number of puzzle objects with the expected solution, category, date,
season, episode, and round for each — verifiable entirely offline against the
fixture.

**Acceptance Scenarios**:

1. **Given** an episode number that exists in the compendium, **When** the user
   requests its puzzles, **Then** the parser returns one puzzle object per row
   recorded for that episode, in the order the rounds aired.
2. **Given** the example episode #8011 (S42, 9/9/24), **When** the user requests
   its puzzles, **Then** the result contains the three puzzles `OPENING NIGHT`
   (Show Biz, T1), `ANIMATED SHORT ATTENTION SPAN` (Before & After, R2), and
   `DIGITAL FOOTPRINT` (Thing, BR), each carrying season 42 and episode 8011.
3. **Given** an episode number that does not exist in the compendium, **When**
   the user requests its puzzles, **Then** the parser returns an empty result
   (no puzzles) rather than failing.

---

### User Story 2 - Each puzzle carries its full, normalized attributes (Priority: P1)

Every returned puzzle exposes, as named attributes: solution, category, date,
season number, episode number, and round. The values are normalized per FORMAT.md
(quotes stripped from solutions, annotation symbols stripped off dates/rounds,
round codes readable) so a consumer can use them directly.

**Why this priority**: The feature explicitly requires a puzzle class with these
attributes. Returning rows without reliable, well-defined fields would not meet
the requirement and would push normalization onto every consumer.

**Independent Test**: For a fixture row containing a quoted solution and an
annotated round (e.g. a prize-puzzle `R3*`), confirm the resulting puzzle object
has the solution without surrounding quotes, the round without the trailing
symbol, and all six attributes populated — verifiable offline.

**Acceptance Scenarios**:

1. **Given** a puzzle row whose solution is wrapped in double quotes, **When**
   it is parsed, **Then** the puzzle's solution attribute contains the text with
   the surrounding quotes removed.
2. **Given** a puzzle row whose date or round cell carries a trailing annotation
   symbol (`*` or `^`), **When** it is parsed, **Then** the corresponding
   attribute holds the clean value with the symbol removed.
3. **Given** any parsed puzzle, **When** its attributes are read, **Then**
   solution, category, date, season number, episode number, and round are all
   present and the season number matches the season page the episode came from.

---

### User Story 3 - Print puzzles during testing (Priority: P2)

When running tests, a developer can opt to print the parsed puzzles for an
episode in a human-readable form, so a failure or unexpected result is
diagnosable from the test log.

**Why this priority**: Required by the feature ("an option in testing to print
out the puzzles") and by the project's debuggable-tests principle, but it is a
testing affordance rather than the core extraction capability, so it ranks below
the P1 stories.

**Independent Test**: Run the test that exercises a fixture episode with the
print option enabled and confirm each puzzle's solution and attributes appear in
the captured test output; run it with the option off and confirm puzzle
solutions are not printed.

**Acceptance Scenarios**:

1. **Given** a parsed set of puzzles in a test, **When** the print option is
   enabled, **Then** each puzzle's attributes (including its solution) are
   written to the test output in a readable form.
2. **Given** normal (non-test) operation, **When** the parser runs, **Then**
   puzzle solutions are NOT printed (solutions surface only behind the test
   boundary).

---

### Edge Cases

- **Episode not found**: an episode number with no rows in the compendium yields
  an empty result, not an error.
- **Episode location**: because the compendium organizes puzzles by season page
  (not by a per-episode page), the feature must determine which season contains
  the requested episode number before it can return that episode's puzzles.
- **Era variation**: episodes from early seasons (no toss-ups, short episode
  numbers like `#5`, unquoted solutions) and recent seasons (toss-ups `T1`–`T5`,
  long numbers like `#8011`, quoted solutions) must both parse correctly.
- **Annotation symbols**: a `*` on a Season 1 date means "bicycling" while a `*`
  on a round means "prize puzzle"; the symbol must be stripped from the value
  regardless, and its meaning not assumed to be singular.
- **Unparseable date**: a date that does not match the expected `M/D/YY` form is
  retained as-is rather than dropped or causing a failure.
- **Source access**: the source site rejects non-browser requests (HTTP 403); a
  retrieval attempt that does not present as a browser must be handled as a
  retrieval failure, distinct from "episode not found".
- **Duplicate/malformed round label**: the rare case of a repeated or malformed
  round within an episode should not collapse two distinct puzzles into one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a Wheel of Fortune episode number as input and
  return the set of puzzles that aired in that episode.
- **FR-002**: System MUST source all puzzle data from the Buy A Vowel Boards
  puzzle compendium at buyavowel.boards.net.
- **FR-003**: System MUST represent each puzzle as an object exposing named
  attributes for: solution, category, date, season number, episode number, and
  round. The `round` attribute MUST hold the clean raw round code (e.g. `T1`,
  `R2`, `BR`) with annotation symbols stripped; the `date` attribute MUST hold
  the normalized ISO `YYYY-MM-DD` string when the source date is parseable and
  the original raw text otherwise.
- **FR-004**: System MUST determine which season's data contains the requested
  episode number by searching compendium season pages and matching the `EP#`
  column; the system owns this lookup end-to-end and MUST NOT require the caller
  to supply the season number.
- **FR-005**: System MUST return all puzzles for the requested episode (every
  round recorded for it), ordered by round as they aired within the episode.
- **FR-006**: System MUST normalize each puzzle solution by removing any
  surrounding quotation marks and surrounding whitespace.
- **FR-007**: System MUST strip trailing annotation symbols (`*`, `^`) from date
  and round values to produce the clean value, and MUST NOT assume a single
  meaning for a given symbol across columns/eras.
- **FR-008**: System MUST set each puzzle's season number from the season the
  episode was found in, and its episode number to the requested episode.
- **FR-009**: System MUST correctly parse episodes across all eras present in the
  compendium (early seasons through the most recent), tolerating the documented
  variations in round set, episode-number width, and solution quoting.
- **FR-010**: System MUST return an empty result (not an error) when the episode
  number exists in no season's data.
- **FR-011**: System MUST distinguish a source-retrieval failure (e.g. the site
  refusing a non-browser request) from a valid "no puzzles found" result.
- **FR-012**: System MUST provide an option, used during testing, to print the
  parsed puzzles (including their solutions) in a human-readable form.
- **FR-013**: System MUST NOT print puzzle solutions during normal (non-test)
  operation; solutions may be emitted only within the test boundary.
- **FR-014**: System MUST consult the conventions documented in FORMAT.md
  (column order, round legend, annotation handling, normalization rules) when
  interpreting compendium data.
- **FR-015**: System MUST keep a date that cannot be parsed into ISO
  `YYYY-MM-DD` as its original text rather than discarding it or failing.
- **FR-016**: System MUST be operable through a command-line interface that
  accepts an episode number and reports the retrieval outcome (puzzle count,
  season, round codes, and source) without revealing puzzle solutions; this CLI
  is the program's user-facing entry point for episode retrieval.

### Key Entities *(include if feature involves data)*

- **Puzzle**: One Wheel of Fortune puzzle from one round of one episode. Key
  attributes: solution (the answer text, normalized), category, date (ISO
  `YYYY-MM-DD` when parseable, else raw source text), season number, episode
  number, and round (clean raw code such as `R2`, symbols stripped). A puzzle is
  uniquely identified within the dataset by the combination of season, episode,
  and round (with solution as a tie-breaker against malformed labels).
- **Episode**: A single broadcast identified by its episode number, belonging to
  one season, containing an ordered set of puzzles (one per round played).
- **Season**: A numbered season of the show whose compendium page holds all
  puzzles for that season; the source from which an episode's season number and
  puzzle rows are derived.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a valid episode number, the system returns every puzzle that
  aired in that episode with 100% of the six required attributes populated for
  each puzzle.
- **SC-002**: For the documented example episode (S42 #8011), the system returns
  exactly the three known puzzles with their correct solutions, categories, and
  rounds.
- **SC-003**: Episodes drawn from early, middle, and recent eras are all parsed
  correctly, with no era failing to yield its puzzles.
- **SC-004**: 100% of returned solutions are free of surrounding quotation marks,
  and 100% of returned date and round values are free of trailing annotation
  symbols.
- **SC-005**: Requesting a non-existent episode returns an empty result with no
  error in 100% of such cases.
- **SC-006**: During normal operation, zero puzzle solutions appear in output;
  during testing with the print option enabled, all puzzle solutions for the
  episode appear in the test log.

## Assumptions

- The episode number provided is the show's global episode number as used in the
  compendium's `EP#` column (e.g. `8011`), not a within-season index.
- Because the compendium has no per-episode page, locating an episode requires
  finding the season whose page contains that episode number; the feature owns
  that lookup by searching season pages and matching the `EP#` column (see
  FR-004), without a caller-supplied season.
- The `date` attribute holds the original air date normalized to ISO
  `YYYY-MM-DD` (per FORMAT.md, with the 2-digit-year pivot at `83`) when
  parseable, and the original raw text when not.
- The six attributes named in the request (solution, category, date, season
  number, episode number, round) are the required surface of the puzzle object;
  annotation flags (`*`/`^`) seen during parsing may be retained separately but
  are not among the six required attributes.
- The feature delivers puzzles as returned objects (a library/function surface);
  building a persistent database or query layer is out of scope for this feature.
- Correctness is validated against saved representative HTML fixtures offline; the
  live site is not required for the test suite to pass.
- The source site requires a real browser User-Agent and is accessed politely;
  retrieval mechanics follow the project's established scraping constraints.

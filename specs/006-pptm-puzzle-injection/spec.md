# Feature Specification: PowerPoint Puzzle Injection

**Feature Branch**: `006-pptm-puzzle-injection`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "Puzzles need to be inserted into WheelofFortune6.4.pptm so they can be played by a group of players where nobody is aware of the puzzle beforehand. Without modifying the VBA code involved with WheelofFortune6.4.pptm, make a copy in the \"games\" folder called \"wof[N].pptm\", where [N] is a three digit number as small as possible without overwriting another file, and use Python code to insert puzzles into the file. There should be four normal round puzzles in slots 1-4, three Toss-Up puzzles in rounds 5-7, and a Bonus Round puzzle in slot 8."

## Clarifications

### Session 2026-06-15

- Q: When the source has more puzzles of a type than the slots need, how are the eight puzzles chosen — and from what scope (episode vs season)? → A: Source by **season** (not a single episode). Pick four Round puzzles at random from the season's Round puzzles, three Toss-Up puzzles at random from the season's Toss-Ups, and one Bonus Round puzzle at random from the season's Bonus Rounds.
- Q: How is the random selection made reproducible for tests and for a host who wants to recreate a game? → A: Random by default; an optional seed input makes the selection deterministic/reproducible.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a ready-to-play game file (Priority: P1)

A host wants a ready-to-play Wheel of Fortune game. They run the tool, which takes
the existing template presentation, fills its eight puzzle slots with real puzzles
(four standard Round puzzles, three Toss-Up puzzles, one Bonus Round puzzle), and
saves the result as a new, uniquely named game file in the `games` folder. The host
can open that file and run the game immediately.

**Why this priority**: This is the entire point of the feature — producing a
playable game from the template. Without it nothing else matters; it is the MVP.

**Independent Test**: Run the tool against the template, open the resulting
`games/wof[N].pptm`, and confirm the eight puzzle slots are populated with the
expected puzzle types in the expected positions and that the game opens and runs.

**Acceptance Scenarios**:

1. **Given** the template presentation exists and the `games` folder is empty,
   **When** the host generates a game, **Then** a file `games/wof001.pptm` is
   created containing the chosen puzzles in their slots, and the original template
   is unchanged.
2. **Given** `games/wof001.pptm` already exists, **When** the host generates
   another game, **Then** the new file is named `games/wof002.pptm` (the smallest
   unused three-digit number) and no existing game file is overwritten.
3. **Given** a generated game file, **When** the host opens it and plays, **Then**
   the game behaves exactly like the template (its interactive behavior is intact)
   with the new puzzles in place.

---

### User Story 2 - Players are not spoiled by the generation step (Priority: P1)

The people generating the game may also be players, so the act of generating a game
must not reveal the puzzle solutions. The tool reports only that a game was created
and where — not the puzzle contents.

**Why this priority**: The stated purpose is that "nobody is aware of the puzzle
beforehand." A generation step that printed the puzzles would defeat the feature
for any host who also plays. Equal priority to US1.

**Independent Test**: Generate a game and inspect everything the tool surfaces to
the operator (its on-screen output and logs); confirm no puzzle solution text
appears.

**Acceptance Scenarios**:

1. **Given** a host generates a game, **When** the tool reports its result, **Then**
   the report names the created file and the count/placement of puzzles but contains
   no solution text.
2. **Given** a host wants to verify a game without spoiling it, **When** they check
   the tool's output, **Then** they can confirm the slots were filled without
   learning any answer.

---

### User Story 3 - Correct puzzle types land in the correct slots (Priority: P2)

The host needs the game to follow Wheel of Fortune's structure: standard Round
puzzles first, then Toss-Ups, then the Bonus Round. The tool must place each puzzle
type in its designated slot so the game plays in the right order.

**Why this priority**: A game with puzzles in the wrong slots is unplayable as
intended. It is P2 because US1 already delivers a populated file; this story pins
the correctness of the placement.

**Independent Test**: Generate a game and confirm slots 1–4 hold standard Round
puzzles, slots 5–7 hold Toss-Up puzzles, and slot 8 holds a Bonus Round puzzle.

**Acceptance Scenarios**:

1. **Given** a generated game, **When** the slots are inspected, **Then** slots 1–4
   each contain one standard Round puzzle.
2. **Given** a generated game, **When** the slots are inspected, **Then** slots 5–7
   each contain one Toss-Up puzzle and slot 8 contains one Bonus Round puzzle.
3. **Given** the supply of available puzzles, **When** a game is generated, **Then**
   no single puzzle appears in more than one slot of that game.

---

### Edge Cases

- **Games folder absent**: if the `games` folder does not exist yet, it is created
  before the first game file is written.
- **Numbering rollover / gaps**: numbering picks the smallest unused three-digit
  value, so a deleted `wof001.pptm` is reused before `wof003.pptm`; behavior at
  `wof999.pptm` (no three-digit number available) is a bounded error, not a silent
  overwrite.
- **Insufficient puzzles**: if the named season does not hold at least four Round,
  three Toss-Up, and one Bonus Round puzzle — because the season is missing or has
  too few of a type — the tool reports a clear error and does not produce a
  partially filled game.
- **Template missing or altered**: if the template presentation is absent, the tool
  reports a clear error rather than producing an empty file.
- **VBA preservation**: the generated file retains the template's macro/interactive
  content unchanged so it still runs as a game.
- **Original untouched**: generating a game never modifies the template
  presentation itself (the template is read-only per generation run; any one-time
  preparation of its slots happens outside generation).
- **Customized template**: if the host has customized the template (e.g. adjusted
  the wheel, restyled, or changed game settings) without removing or renaming the
  eight puzzle slots, those customizations are carried into every generated game and
  puzzle placement is unaffected. If a customization removes a puzzle slot, the tool
  reports a clear error rather than producing a malformed game.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST produce a new game file from the template
  presentation without modifying the template **during generation** (each
  generation run treats the template as read-only). Preparing the template once as a
  setup step — so its eight puzzle slots can be reliably located — is a separate,
  one-time action distinct from generation and MUST NOT touch the macro/VBA content
  (see FR-004).
- **FR-002**: The system MUST write the new game file into the `games` folder,
  creating that folder if it does not exist.
- **FR-003**: The system MUST name the new file `wof[N].pptm`, where `[N]` is a
  three-digit, zero-padded number that is the smallest value not already used by an
  existing file in the `games` folder (so existing game files are never
  overwritten).
- **FR-004**: The system MUST NOT modify the macro/interactive (VBA) content of the
  presentation; the generated game MUST retain the template's interactive behavior.
- **FR-005**: The system MUST place exactly eight puzzles into the game: four
  standard Round puzzles in slots 1–4, three Toss-Up puzzles in slots 5–7, and one
  Bonus Round puzzle in slot 8.
- **FR-006**: Each puzzle slot MUST receive a puzzle of the type designated for that
  slot (Round, Toss-Up, or Bonus Round).
- **FR-007**: Within a single generated game, no puzzle MUST appear in more than one
  slot.
- **FR-008**: The system MUST source its puzzles from a host-specified **season**
  in the project's ingested puzzle store (not a single episode). It MUST select, at
  random from that season's puzzles, four Round puzzles for slots 1–4, three Toss-Up
  puzzles for slots 5–7, and one Bonus Round puzzle for slot 8 — eight distinct
  puzzles drawn independently per type. If the named season is not present in the
  store, the system MUST report a clear error and produce no game file.
- **FR-009**: The generation step MUST NOT reveal any puzzle solution **or
  category** in its operator-facing output, including error messages (a category
  can itself hint the answer); it reports only the created file and the
  count/placement of puzzles. This applies to all operator-facing output (standard
  output, errors, and logs), consistent with the project's no-spoilers rule.
- **FR-010**: If the named season cannot supply the required number of puzzles of
  each type (at least four Round, three Toss-Up, and one Bonus Round), the system
  MUST report a clear error and MUST NOT produce a partially populated game file.
- **FR-011**: If no three-digit file number is available (all `wof001`–`wof999`
  used), the system MUST report a clear error rather than overwrite an existing
  file.
- **FR-012**: Puzzle selection MUST be random by default. The system MUST accept an
  optional seed; when a seed is supplied, the selection MUST be deterministic and
  reproducible (the same season and seed yield the same eight puzzles), so a run can
  be recreated and the behavior can be tested exactly.
- **FR-013**: Puzzle placement MUST be robust to template customization: locating the
  eight slots MUST NOT depend on slide/shape ordering, so host edits elsewhere in the
  template (and re-saving it) do not misplace puzzles, and such customizations are
  preserved in the generated game. If a slot can no longer be located (it was removed
  or renamed), the system MUST report a clear error and MUST NOT produce a malformed
  game.

### Key Entities *(include if feature involves data)*

- **Template presentation**: the existing `WheelofFortune6.4.pptm` game shell,
  including its interactive/macro content and eight puzzle slots that hold no real
  puzzle until a game is generated (a one-time setup may place neutral placeholder
  markers in those slots so they can be located). Treated as read-only input during
  every generation run; never modified when a game is produced.
- **Game file**: a generated `games/wof[N].pptm` — a copy of the template with its
  eight slots filled. The deliverable a host opens and plays.
- **Puzzle**: a single Wheel of Fortune puzzle with a solution, a category, and a
  type (Round, Toss-Up, or Bonus Round). The type determines which slot range a
  puzzle is eligible for.
- **Puzzle slot**: one of eight ordered positions in the game (1–4 Round, 5–7
  Toss-Up, 8 Bonus Round), each holding exactly one puzzle.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A host can produce a ready-to-play game file in a single action,
  with no manual editing of the presentation afterward.
- **SC-002**: Generating a game when `N` files already exist always produces the
  next file at the smallest unused three-digit number and overwrites zero existing
  files (verified across repeated runs).
- **SC-003**: 100% of generated games have slots 1–4 as Round, 5–7 as Toss-Up, and
  8 as Bonus Round, with eight distinct puzzles.
- **SC-004**: Generated games open and run with the same interactive behavior as the
  template in 100% of runs (the macro content is intact).
- **SC-005**: No puzzle solution or category is exposed in operator-facing output
  during generation (success or error), in zero out of all generation runs.
- **SC-006**: Two generations from the same season with the same seed produce the
  same eight puzzles in the same slots; with no seed (or different seeds), the
  lineup varies across runs.

## Assumptions

- "Slots 1–4 / rounds 5–7 / slot 8" refer to the eight ordered puzzle positions the
  template game already defines; "normal round" means a standard Round puzzle (as
  opposed to a Toss-Up or the Bonus Round), matching the puzzle types this project
  already records.
- One game file is produced per generation run; producing many games means running
  the tool repeatedly, each yielding the next-numbered file.
- The host names a season; the tool fills the eight slots with puzzles drawn at
  random by type from that season (four Round, three Toss-Up, one Bonus Round), so
  successive games from the same season generally differ and the lineup does not
  reproduce any one episode.
- The puzzle store is the one this project already produces (via ingest); a populated
  store covering the requested season is a prerequisite for generating a game.
- The `games` folder lives at the project root (a sibling of the template) unless
  configured otherwise.
- The generated game is the unit of delivery; editing or curating individual slots
  by hand after generation is out of scope for this feature.
- The host has the means to open and run a macro-enabled presentation; enabling
  macros in the player's application is the host's responsibility, not this tool's.

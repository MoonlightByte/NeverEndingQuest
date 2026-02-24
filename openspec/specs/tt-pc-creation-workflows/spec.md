## Purpose

Define deterministic tabletop-friendly PC creation workflows across startup, Create with DM, and Roll Your Own paths while preserving single-player compatibility.

## Requirements

### Requirement: Campaign initiation SHALL support iterative multi-PC onboarding

The startup character-creation workflow SHALL support creating one or more player characters in sequence for tabletop sessions. After each successful character creation, the workflow SHALL prompt whether to create another player and SHALL append each accepted character to `partyMembers` without overwriting previously created members.

#### Scenario: DM creates multiple PCs at campaign start
- **WHEN** startup character creation completes for the first player and the DM indicates another player is joining
- **THEN** the system prompts for the next player and repeats creation until the DM declines

#### Scenario: Single-player startup remains valid
- **WHEN** startup character creation completes and the DM declines additional players
- **THEN** startup finalizes with one character and behavior remains backward-compatible with existing single-player flow

#### Scenario: Loop recovery on failed secondary creation
- **WHEN** a secondary player-creation attempt fails validation
- **THEN** the system reports the failure, preserves already-created party members, and allows retry or graceful exit without corrupting `partyMembers`

#### Scenario: Add-more prompt is line-visible in web startup flow
- **WHEN** first PC creation succeeds during startup in web mode
- **THEN** the add-more question is emitted as line-visible output before input collection

#### Scenario: Blank or invalid add-more decision reprompts
- **WHEN** facilitator enters blank input (including timeout-injected blank) or non-yes/no text
- **THEN** startup shows valid options and reprompts without advancing to gameplay

#### Scenario: Startup exits additional-PC loop only on explicit no
- **WHEN** facilitator enters `n` or `no` at add-more or retry decision points
- **THEN** startup exits additional-PC loop and proceeds to party tracker finalization

### Requirement: Mid-campaign Add Existing SHALL exclude current party members

The Add Existing character list API SHALL return only available player characters not currently present in `party_tracker.partyMembers`, and SHALL deduplicate entries found across scanned character locations.

#### Scenario: Existing party members are filtered out
- **WHEN** the DM opens Add Existing mid-campaign
- **THEN** characters already in `partyMembers` are not returned in the selectable list

#### Scenario: Duplicate character files across scan paths
- **WHEN** the same player character is discovered in more than one scanned directory
- **THEN** the API returns one deduplicated entry for that character

#### Scenario: No available candidates
- **WHEN** all discovered player characters are already in party or invalid
- **THEN** the API returns an empty list and the UI displays a no-unused-characters state

### Requirement: Create with DM SHALL finalize only schema-valid complete characters

The DM interview flow SHALL finalize character creation only after extracting a complete final JSON payload that passes schema validation and completeness audit, including authored `backstory`.

#### Scenario: Valid final JSON from interview
- **WHEN** the LLM returns a final character JSON that satisfies schema and completeness requirements including `backstory`
- **THEN** the system saves the character, updates party state, and exits creation mode

#### Scenario: Invalid or incomplete final JSON
- **WHEN** the LLM returns malformed JSON or missing required completeness fields (including `backstory`)
- **THEN** the system keeps creation mode active, emits corrective guidance with missing or invalid fields, and requests corrected final output

#### Scenario: Code-fenced JSON final response
- **WHEN** the LLM returns final JSON in a fenced code block
- **THEN** the system extracts and validates the payload using the same finalization rules as raw JSON

### Requirement: Roll Your Own SHALL support both create and edit entry points
The Roll Your Own workflow SHALL support both create mode (existing Manage Party flow) and edit mode (new Character Sheet `Edit` entry) while preserving create semantics.

#### Scenario: Create mode remains unchanged
- **WHEN** Roll Your Own is opened from Manage Party for a new character
- **THEN** submit continues to use the create path and create-only side effects remain as currently defined

#### Scenario: Edit mode uses existing character context
- **WHEN** Roll Your Own is opened from Character Sheet `Edit`
- **THEN** form mode is edit, existing values are prefilled, and submit routes to the deterministic edit path

#### Scenario: Name safety in MVP edit mode
- **WHEN** Roll Your Own is opened in edit mode
- **THEN** character name is treated as fixed identity input (read-only or equivalent guarded behavior)

### Requirement: Roll Your Own SHALL replace DM Quick-Create with sheet-aligned sections

The manual creation tab SHALL be renamed to Roll Your Own and SHALL collect enough structured fields to map to major 5e character sheet sections before server-side normalization and validation.

#### Scenario: Manual sheet-aligned creation includes backstory
- **WHEN** the DM completes Roll Your Own form and submits
- **THEN** payload includes `backstory`, backend validates schema and completeness, and persistence proceeds only on success

#### Scenario: Manual submission missing required sections
- **WHEN** Roll Your Own submission omits required data
- **THEN** the system rejects save with clear validation errors and does not create a partial character file

#### Scenario: Manual submission missing backstory
- **WHEN** Roll Your Own submission omits `backstory`
- **THEN** save is blocked with completeness errors and no partial character file is created

#### Scenario: Backward-compatible low-detail submission path
- **WHEN** a minimal manual payload is submitted through legacy fields
- **THEN** server-side normalization fills deterministic defaults and still requires final schema-valid completion before save

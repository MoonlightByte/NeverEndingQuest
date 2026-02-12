## ADDED Requirements

### Requirement: Campaign initiation SHALL support iterative multi-PC onboarding
The startup character creation workflow SHALL support creating one or more player characters in sequence for tabletop sessions. After each successful character creation, the workflow SHALL prompt whether to create another player character and SHALL append each accepted character to `partyMembers` without overwriting previously created members.

#### Scenario: DM creates multiple PCs at campaign start
- **WHEN** startup character creation completes for the first player and the DM indicates another player is joining
- **THEN** the system prompts for the next player and repeats creation until the DM declines

#### Scenario: Single-player startup remains valid
- **WHEN** startup character creation completes and the DM declines additional players
- **THEN** startup finalizes with one character and behavior remains backward-compatible with existing single-player flow

#### Scenario: Loop recovery on failed secondary creation
- **WHEN** a secondary player creation attempt fails validation
- **THEN** the system reports the failure, preserves already-created party members, and allows retry or graceful exit without corrupting `partyMembers`

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
The DM interview flow SHALL finalize character creation only after extracting a complete final JSON payload that passes schema validation and completeness audit. Partial, malformed, or mismatched payloads SHALL NOT be saved as character files.

#### Scenario: Valid final JSON from interview
- **WHEN** the LLM returns a final character JSON that satisfies schema and completeness requirements
- **THEN** the system saves the character, updates party state, and exits creation mode

#### Scenario: Invalid or incomplete final JSON
- **WHEN** the LLM returns malformed JSON or missing required fields
- **THEN** the system keeps creation mode active, emits corrective guidance with missing/invalid fields, and requests corrected final output

#### Scenario: Code-fenced JSON final response
- **WHEN** the LLM returns final JSON in a fenced code block
- **THEN** the system extracts and validates the payload using the same finalization rules as raw JSON

### Requirement: Roll Your Own SHALL replace DM Quick-Create with sheet-aligned sections
The manual creation tab SHALL be renamed to Roll Your Own and SHALL collect enough structured fields to map to major 5e character sheet sections before server-side normalization and validation.

#### Scenario: Manual sheet-aligned creation
- **WHEN** the DM completes Roll Your Own form and submits
- **THEN** the backend normalizes the payload, validates schema/completeness, and only then persists and adds to party

#### Scenario: Manual submission missing required sections
- **WHEN** Roll Your Own submission omits required data
- **THEN** the system rejects save with clear validation errors and does not create a partial character file

#### Scenario: Backward-compatible low-detail submission path
- **WHEN** a minimal manual payload is submitted through legacy fields
- **THEN** server-side normalization fills deterministic defaults and still requires final schema-valid completion before save

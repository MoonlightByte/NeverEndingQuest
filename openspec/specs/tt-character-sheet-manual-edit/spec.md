## Purpose

Define deterministic edit capabilities for Character Sheet Roll Your Own workflow, ensuring safe in-sheet editing without side effects.

## Requirements

### Requirement: Character Sheet SHALL expose Roll Your Own edit entry
The character sheet UI SHALL expose an `Edit` action adjacent to existing sheet actions, and SHALL position `Edit` before `Download PDF` in one row.

#### Scenario: Action row order is deterministic
- **WHEN** character sheet stats are rendered
- **THEN** the action row includes `Edit` followed by `Download PDF` in that order

#### Scenario: Edit entry is available during normal sheet use
- **WHEN** a player or facilitator views a loaded character sheet
- **THEN** the `Edit` action is visible and clickable without opening Manage Party first

### Requirement: Edit entry SHALL open existing Roll Your Own form with prefilled active-PC values
The `Edit` action SHALL reuse the existing Roll Your Own form and SHALL prefill fields from the currently displayed active PC.

#### Scenario: Edit opens Roll Your Own in edit mode
- **WHEN** user clicks `Edit` from character sheet
- **THEN** the system opens Manage Party modal, activates the Roll Your Own tab, and sets form mode to edit

#### Scenario: Prefill uses active character data
- **WHEN** edit mode initializes
- **THEN** Roll Your Own fields are prefilled from active character data for all mapped fields

### Requirement: Edit submit SHALL update existing PC deterministically without party mutation
Roll Your Own edit submit SHALL update the existing character record only and SHALL NOT trigger create-only side effects.

#### Scenario: Successful edit updates existing character file
- **WHEN** user submits valid edit payload
- **THEN** the existing character file is updated and no new character file is created

#### Scenario: Edit path does not alter party membership
- **WHEN** edit submit succeeds
- **THEN** `partyMembers` and `active_character` remain unchanged

#### Scenario: Edit path does not enqueue create-only intro prompts
- **WHEN** edit submit succeeds
- **THEN** no character-creation intro prompt is queued

### Requirement: Edit flow SHALL preserve non-targeted character state
Edit operations SHALL update only mapped form-backed fields and SHALL preserve non-targeted nested state.

#### Scenario: Complex nested fields remain intact
- **WHEN** edit payload omits non-form structures (for example advanced spell lists or feature metadata)
- **THEN** those existing structures remain unchanged after save

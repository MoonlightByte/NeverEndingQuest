## Purpose

Provide clear, contextual UX guidance for authored character-profile narrative fields so players can confidently fill meaningful values without external rules lookup.

## Requirements

### Requirement: Portrait profile modal SHALL collect Backstory instead of background-feature fields

The portrait Create profile modal SHALL require a `Backstory` field for narrative identity and SHALL no longer require `backgroundFeature.name` and `backgroundFeature.description` in that modal flow.

#### Scenario: Portrait profile modal guidance
- **WHEN** the user opens the portrait profile modal
- **THEN** the modal displays a required `Backstory` field with guidance-oriented placeholder text
- **AND** submitted payload persists `backstory` before portrait generation

### Requirement: Character creation surfaces SHALL continue guided background-feature entry

Character creation forms that explicitly manage background-feature data SHALL continue to show guided examples for `backgroundFeature.name` and `backgroundFeature.description`.

#### Scenario: Roll Your Own guidance preserved
- **WHEN** the user opens manual character creation inputs
- **THEN** background-feature labels and placeholders remain guidance-oriented and custom authored values are preserved

### Requirement: Guided examples MUST remain non-prescriptive

The system MUST allow player-authored custom background-feature text and MUST NOT force a strict canonical phrase list.

#### Scenario: User enters custom background-feature text
- **WHEN** a user submits non-generic custom text for name and description
- **THEN** the system persists those values unchanged

### Requirement: Known background suggestions SHALL prefill only blank or generic values

For known backgrounds with deterministic mappings, the system SHALL suggest default `backgroundFeature` content only when fields are blank or match generic placeholder patterns.

#### Scenario: Known background with generic placeholder fields
- **WHEN** background is recognized and current background-feature fields are blank or generic placeholders
- **THEN** the system pre-fills deterministic suggestion values before save/create

#### Scenario: Known background with authored values
- **WHEN** background is recognized and user-authored non-generic values already exist
- **THEN** the system preserves authored values and does not overwrite them

## ADDED Requirements

### Requirement: Background feature inputs SHALL provide explicit guided examples
Character profile entry surfaces SHALL provide clear guidance for `backgroundFeature.name` and `backgroundFeature.description` so players can author meaningful values without external rules lookup.

#### Scenario: Portrait profile modal guidance
- **WHEN** the user opens the portrait profile modal
- **THEN** `Background Feature Name` displays example-oriented guidance (for example `Criminal Contact`, `Researcher`)
- **AND** `Background Feature Description` displays guidance to write `1-3 sentences` describing practical in-world access or benefit

#### Scenario: Character creation form guidance
- **WHEN** the user opens manual character creation inputs
- **THEN** background feature labels/placeholders use the same guidance contract as portrait profile modal

### Requirement: Guided examples MUST remain non-prescriptive
The system MUST allow player-authored custom background feature text and MUST NOT force a strict canonical phrase list.

#### Scenario: User enters custom background feature text
- **WHEN** a user submits non-generic custom text for name and description
- **THEN** the system persists those values unchanged

### Requirement: Known background suggestions SHALL prefill only blank or generic values
For known backgrounds with deterministic mappings, the system SHALL suggest default `backgroundFeature` content only when fields are blank or match generic placeholder patterns.

#### Scenario: Known background with generic placeholder fields
- **WHEN** background is recognized and current background feature fields are blank or generic placeholders
- **THEN** the system pre-fills deterministic suggestion values before save/create

#### Scenario: Known background with authored values
- **WHEN** background is recognized and user-authored non-generic values already exist
- **THEN** the system preserves authored values and does not overwrite them

### SHOULD Guidance
- Guidance copy SHOULD stay short enough to remain readable on narrow sidebar/modal layouts.
- Suggested examples SHOULD include both social-access and knowledge-access patterns to reduce player ambiguity.

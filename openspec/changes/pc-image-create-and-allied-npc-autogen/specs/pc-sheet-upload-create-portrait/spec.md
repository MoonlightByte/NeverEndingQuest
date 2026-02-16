## ADDED Requirements

### Requirement: Character Sheet SHALL expose Upload and Create portrait actions

Character Sheet portrait controls SHALL provide both Upload and Create actions for player-facing portrait management.

#### Scenario: Open Character Sheet portrait control
- **WHEN** a user opens Character Sheet and interacts with portrait controls
- **THEN** both `Upload` and `Create` actions are available

### Requirement: Upload portrait behavior MUST remain backward compatible

Existing upload workflow MUST continue to function without behavioral regression.

#### Scenario: Upload portrait via existing flow
- **WHEN** a user selects Upload and submits a valid image
- **THEN** portrait updates successfully using existing upload semantics

### Requirement: Create portrait SHALL generate and persist canonical portrait assets

Create action SHALL call a backend portrait generation path and save assets in expected locations.

#### Scenario: Create portrait success path
- **WHEN** a user triggers Create for a valid character
- **THEN** backend generates portrait output and writes canonical portrait assets
- **AND** response returns a success payload usable for immediate UI refresh

### Requirement: Create portrait failures SHALL be failure-isolated

Portrait create failures SHALL return safe errors and SHALL NOT break gameplay/session flow.

#### Scenario: Create portrait provider failure
- **WHEN** generation fails due to provider or IO error
- **THEN** API returns safe error response
- **AND** existing portrait/fallback remains usable

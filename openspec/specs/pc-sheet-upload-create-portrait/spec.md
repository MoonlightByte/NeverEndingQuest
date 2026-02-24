## Purpose

Define Character Sheet portrait management contracts for Upload/Create actions, profile-first create flow, and failure-isolated generation behavior.

## Requirements

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

### Requirement: Create portrait SHALL always open full-profile modal before submission

Character Sheet portrait `Create` action SHALL always open a modal that allows editing portrait-driving profile fields before generation.

#### Scenario: Create clicked from Character Sheet
- **WHEN** user clicks portrait `Create`
- **THEN** full-profile modal opens every time
- **AND** modal inputs are prefilled from current character data

### Requirement: Create modal submission SHALL enforce complete profile fields

Create modal SHALL block submission until all required profile fields are non-empty (trimmed).

#### Scenario: Missing required field in modal
- **WHEN** any required profile field is blank
- **THEN** submit is blocked with safe validation feedback

### Requirement: Create submission SHALL persist profile edits before generation

Profile edits submitted through create modal SHALL be persisted to character state prior to portrait generation.

#### Scenario: Modal submit with profile edits
- **WHEN** user submits full-profile modal
- **THEN** profile fields are saved to character JSON
- **AND** portrait generation uses updated saved values
- **AND** sheet refresh reflects updated fields after success

### Requirement: Create portrait failures SHALL be failure-isolated

Portrait create failures SHALL return safe errors and SHALL NOT break gameplay/session flow.

#### Scenario: Create portrait provider failure
- **WHEN** generation fails due to provider or IO error
- **THEN** API returns safe error response
- **AND** existing portrait or fallback remains usable

### Requirement: NPC to PC promotion SHALL remain viable without forced portrait replacement

Promotion through Manage Party/Add Existing SHALL keep portrait continuity and SHALL NOT require immediate portrait recreation to complete the role transition.

#### Scenario: Promote NPC companion with existing NPC media only
- **WHEN** user promotes an NPC companion to player role
- **THEN** promotion completes using the same character identity/file
- **AND** Character Sheet portrait resolution remains functional through existing fallback chain without requiring image regeneration

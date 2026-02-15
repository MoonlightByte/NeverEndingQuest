## ADDED Requirements

### Requirement: Save workflow SHALL snapshot memory DB alongside gameplay state
The system SHALL include a memory DB package artifact in each save game so memory state is captured with the same snapshot boundary as JSON gameplay files.

#### Scenario: Save creates memory package
- **WHEN** a save is created successfully
- **THEN** the save folder contains a memory DB package artifact and manifest
- **AND** save metadata records package creation status

### Requirement: Restore workflow SHALL import memory package before completion
The system SHALL restore memory DB state from the selected save package before signaling restore completion.

#### Scenario: Restore with valid memory package
- **WHEN** operator restores a save containing a valid memory package
- **THEN** memory DB is imported from that package
- **AND** restore completion is emitted only after import succeeds

#### Scenario: Restore excludes package artifact from runtime copy
- **WHEN** restore copies gameplay files from save directory back to runtime paths
- **THEN** `memory_db_package/` is excluded from the generic file-copy loop
- **AND** memory package content is handled only by managed import workflow

### Requirement: Restore SHALL prevent JSON-memory divergence on package failure
The system MUST prevent successful restore completion if the selected save has a memory package that fails integrity or compatibility validation.

#### Scenario: Corrupt memory package during restore
- **WHEN** restore targets a save with a corrupt or incompatible memory package
- **THEN** restore fails with an explicit error outcome
- **AND** completion/restart signaling is not emitted as successful

#### Scenario: Package failure fails before restore mutations
- **WHEN** restore preflight detects memory package validation failure
- **THEN** restore exits with failure before backup, directory cleanup, or gameplay file overwrite begins
- **AND** runtime JSON and memory state remain unchanged by that failed restore attempt

### Requirement: Legacy save restore SHALL use deterministic memory fallback
The system SHALL use a deterministic fallback path when restoring legacy saves that do not include memory package artifacts.

#### Scenario: Restore of legacy save without memory package
- **WHEN** restore targets a save that predates memory package parity
- **THEN** memory DB is re-initialized to a known baseline state
- **AND** restore metadata records that legacy fallback mode was used

### Requirement: Save parity errors SHALL be explicit under managed parity mode
When memory parity integration is enabled and a source memory DB exists, save creation MUST report failure if memory package export fails.

#### Scenario: Save fails on export error with parity enabled
- **WHEN** save creation runs with parity enabled and source memory DB present
- **AND** memory package export fails
- **THEN** save operation returns failure status
- **AND** metadata does not claim successful memory parity for that save

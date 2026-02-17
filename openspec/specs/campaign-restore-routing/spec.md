# campaign-restore-routing Specification

## Purpose
TBD - created by archiving change archive-global-save-index-and-restore-routing. Update Purpose after archive.
## Requirements
### Requirement: Restore routing SHALL support cross-module save selection
The restore workflow SHALL accept a validated save target that identifies both source module and save folder so restores can run independent of the active module.

#### Scenario: Restore from non-active module save
- **WHEN** the active module differs from the selected save's source module
- **THEN** restore executes successfully against the selected module save folder without requiring manual module reconfiguration

### Requirement: Restore routing SHALL reject invalid save target paths
The system SHALL validate cross-module restore targets and reject any request that does not resolve to `modules/<module>/saved_games/save_*`.

#### Scenario: Path traversal attempt is rejected
- **WHEN** a restore request contains an invalid module or folder component that would resolve outside allowed save directories
- **THEN** restore returns a failure outcome and does not mutate runtime files

### Requirement: Cross-module restore SHALL preserve memory parity safety checks
Cross-module restore SHALL run existing memory package preflight and managed import behavior before restore completion.

#### Scenario: Invalid memory package blocks restore
- **WHEN** a selected cross-module save contains a corrupt or incompatible memory package
- **THEN** restore fails before backup, cleanup, or file overwrite operations begin


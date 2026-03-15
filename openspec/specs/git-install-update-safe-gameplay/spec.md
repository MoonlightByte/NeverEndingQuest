# git-install-update-safe-gameplay Specification

## Purpose
TBD - created by archiving change module-data-git-fix. Update Purpose after archive.
## Requirements
### Requirement: Ordinary gameplay SHALL NOT dirty tracked repository content
Runtime gameplay mutations in a Git install SHALL be confined to runtime-local state so ordinary play does not create tracked repo dirtiness.

#### Scenario: Plot advancement updates runtime state only
- **WHEN** gameplay advances plot points or quest progression during a session
- **THEN** the resulting mutations SHALL apply to runtime-local files only
- **AND** tracked canonical module content SHALL remain unchanged by the gameplay action

#### Scenario: Area reconciliation updates runtime state only
- **WHEN** gameplay systems reconcile location state, monster state, or NPC movement during play
- **THEN** those writes SHALL target runtime-local live files only
- **AND** tracked canonical backups SHALL remain unchanged

### Requirement: Git installs SHALL remain update-ready after ordinary play
A player using a Git install SHALL be able to continue using fast-forward update workflows after ordinary gameplay when no code edits exist.

#### Scenario: Fresh clone remains update-safe after representative play
- **WHEN** a fresh Git clone boots, completes startup, and performs representative gameplay mutations without developer code edits
- **THEN** tracked-tree cleanliness SHALL remain available for normal update workflows
- **AND** the install SHALL NOT require stashing or resetting gameplay state just to take a fast-forward update

### Requirement: Runtime-state cleanup SHALL preserve SP and TABLETOP MODE compatibility
The runtime/canonical split SHALL preserve current single-player and TABLETOP MODE behavior.

#### Scenario: Same runtime-state boundary works in both play modes
- **WHEN** startup, reset, and normal gameplay execute in either single-player or TABLETOP MODE
- **THEN** the canonical-vs-runtime file boundary SHALL remain consistent
- **AND** the cleanup SHALL NOT require separate file families for the two play modes


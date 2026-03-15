# module-runtime-state-hydration Specification

## Purpose
TBD - created by archiving change module-data-git-fix. Update Purpose after archive.
## Requirements
### Requirement: Startup and reset SHALL hydrate missing live module files from canonical backups
Fresh installs and reset flows SHALL recreate missing live mutable module files from tracked canonical sources before gameplay depends on them.

#### Scenario: Missing live area file is recreated from `_BU`
- **WHEN** startup or reset detects that a required live `areas/*.json` file is missing
- **THEN** the system SHALL recreate the live file from the matching tracked `*_BU.json` source
- **AND** gameplay systems SHALL continue using the live runtime filename after hydration

#### Scenario: Missing live module plot is recreated from `_BU`
- **WHEN** startup or reset detects that `module_plot.json` is missing for the active module
- **THEN** the system SHALL recreate the live file from tracked `module_plot_BU.json`
- **AND** runtime plot progression SHALL continue using the live `module_plot.json` path after hydration

### Requirement: Derived runtime projections SHALL regenerate when absent
Derived runtime files SHALL be recreated deterministically when they are missing rather than requiring tracked live copies.

#### Scenario: Missing player quest projection is regenerated
- **WHEN** gameplay or UI paths need `player_quests_<module>.json` and the file is absent
- **THEN** the system SHALL regenerate the projection from current runtime state
- **AND** the missing derived file SHALL NOT block fresh-install or reset playability

### Requirement: Canonical backup coverage SHALL be complete before live files are untracked
The system SHALL NOT rely on untracked live files as the only remaining copy of mutable module content.

#### Scenario: Module lacks canonical backup coverage
- **WHEN** a shipped module is missing required `_BU` coverage for a live mutable area or module plot file
- **THEN** tracking cleanup for that file family SHALL stop until canonical coverage is added
- **AND** rollout SHALL treat the missing backup as a blocker rather than silently proceeding


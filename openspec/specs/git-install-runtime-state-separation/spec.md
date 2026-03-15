# git-install-runtime-state-separation Specification

## Purpose
TBD - created by archiving change module-data-git-fix. Update Purpose after archive.
## Requirements
### Requirement: Git installs SHALL separate canonical module content from mutable runtime state
The repository SHALL classify canonical shipped content separately from mutable gameplay state so Git installs do not depend on runtime-mutated files being tracked.

#### Scenario: Mutable area and plot files are treated as runtime state
- **WHEN** a module file family is both shipped and mutated during live gameplay
- **THEN** the live runtime copy SHALL be treated as mutable local state
- **AND** canonical shipped content SHALL come from tracked authored files or tracked `_BU` backups rather than the live mutable copy

#### Scenario: Canonical shipped content remains tracked
- **WHEN** a file family represents authored module content needed for fresh installs
- **THEN** the canonical source SHALL remain tracked in Git
- **AND** runtime cleanup SHALL NOT remove tracked authored files, tracked `_BU` backups, or other intentionally canonical module assets

### Requirement: Root bootstrap state SHALL be treated as runtime local state
Root campaign bootstrap files that are created or updated during local play SHALL be treated as runtime local state rather than required shipped content.

#### Scenario: Fresh clone starts without root runtime state
- **WHEN** a fresh Git clone lacks `party_tracker.json` or equivalent bootstrap state
- **THEN** startup SHALL treat that absence as bootstrap-required local state
- **AND** it SHALL NOT classify the install as broken solely because the runtime file is missing

### Requirement: Derived gameplay projections SHALL NOT be canonical Git inputs
Derived projections that are regenerated from canonical gameplay state SHALL be treated as runtime outputs rather than canonical tracked inputs.

#### Scenario: Player quest projection is regenerated
- **WHEN** `player_quests_<module>.json` is missing or stale
- **THEN** the system SHALL regenerate it from canonical runtime state and plot data
- **AND** Git tracking SHALL NOT depend on the projection file being the canonical source of truth


# homebrew-monster-prewarm-reuse-first Specification

## Purpose
TBD - created by archiving change monster-prewarm-bestiary-reuse-first. Update Purpose after archive.
## Requirements
### Requirement: Monster prewarm SHALL be reuse-first and portrait-lane safe

Homebrew monster prewarm SHALL resolve existing monster media before generation and SHALL not write monster outputs into character portrait paths.

#### Scenario: Existing static monster media is reused

- **WHEN** monster media exists in static/bestiary media paths
- **THEN** prewarm SHALL reuse those assets for module readiness
- **AND** provider generation SHALL NOT be invoked for that monster

#### Scenario: Existing module monster media is reused

- **WHEN** module-local monster media already exists
- **THEN** prewarm SHALL mark that monster as reused/skipped
- **AND** no generation/write SHALL occur for that entity

#### Scenario: No portrait-lane contamination

- **WHEN** prewarm processes monsters
- **THEN** it SHALL NOT write to `web/static/portraits`
- **AND** it SHALL NOT write to active module `portraits/` directories


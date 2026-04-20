# homebrew-monster-prewarm-provider-fallback Specification

## Purpose
TBD - created by archiving change monster-prewarm-bestiary-reuse-first. Update Purpose after archive.
## Requirements
### Requirement: Monster fallback generation SHALL be explicit and monster-specific

When reusable monster media is unavailable, generation fallback SHALL remain opt-in and SHALL use monster-specific generation flow.

#### Scenario: Provider disabled

- **WHEN** prewarm runs without `--allow-provider`
- **AND** a monster has no reusable media
- **THEN** prewarm SHALL not call provider generation
- **AND** result SHALL report skipped/degraded for that entity

#### Scenario: Provider enabled

- **WHEN** prewarm runs with `--allow-provider`
- **AND** a monster has no reusable media
- **THEN** fallback generation SHALL run through monster generator tooling
- **AND** generation SHALL NOT route through character portrait prompt/service paths

### Requirement: Toolkit-facing reporting SHALL preserve provider opt-in semantics for monster media debt
Toolkit-facing prewarm, finisher, and reporting flows SHALL preserve the explicit provider opt-in monster media contract when reusable media is unavailable.

#### Scenario: Provider-disabled toolkit flow reports non-generated monster media debt
- **GIVEN** reusable monster media cannot be found for a combat-valid structured monster
- **AND** the toolkit flow did not enable provider generation
- **WHEN** toolkit-facing reporting evaluates monster media outcome
- **THEN** the result SHALL report that provider generation was disabled and media remains unresolved
- **AND** SHALL keep that state distinct from generation-attempted failure
- **AND** SHALL identify existing toolkit manual image-generation surfaces as the next remediation step

#### Scenario: Provider-enabled toolkit flow distinguishes attempted unresolved media
- **GIVEN** reusable monster media cannot be found for a combat-valid structured monster
- **AND** the toolkit flow enabled provider generation
- **WHEN** generation still fails to produce required module-local base media
- **THEN** reporting SHALL distinguish that attempted unresolved result from provider-disabled non-generation


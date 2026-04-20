# homebrew-monster-prewarm-provider-fallback Specification Delta

## ADDED Requirements

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

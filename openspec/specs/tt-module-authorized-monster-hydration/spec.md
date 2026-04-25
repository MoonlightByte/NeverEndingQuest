# tt-module-authorized-monster-hydration Specification

## Purpose
TBD - created by archiving change module-authorized-monster-hydration. Update Purpose after archive.
## Requirements
### Requirement: Module-authorized monsters SHALL be hydratable at encounter time
Encounter creation SHALL allow a missing monster stat file to be materialized only when that monster can be validated against authored module content.

#### Scenario: Authorized standard monster is missing local stat file
- **WHEN** `createEncounter` references a monster whose normalized name is authorized by authored content in the active module
- **AND** `modules/<module>/monsters/<normalized_name>.json` does not exist
- **THEN** runtime resolution SHALL treat the monster as `authorized_missing`
- **AND** the system SHALL attempt reuse-first or builder hydration before failing the encounter

#### Scenario: Existing local monster file remains authoritative
- **WHEN** `createEncounter` references a monster whose module-local stat file already exists
- **THEN** the system SHALL use the existing local file without invoking hydration
- **AND** encounter startup behavior SHALL remain backward compatible

### Requirement: Runtime authorization SHALL derive from authored module content only
Monster authorization for runtime hydration SHALL come from authored module assets, not freeform runtime narration.

#### Scenario: Authored module content authorizes a creature
- **WHEN** a normalized monster identity is present in authored module sources used by the authorization roster
- **THEN** encounter creation SHALL treat that identity as eligible for hydration if its local file is missing

#### Scenario: Runtime narration alone does not authorize a creature
- **WHEN** a monster appears only in live model narration or chat history
- **AND** the active module content does not authorize that normalized identity
- **THEN** encounter creation SHALL reject it as unauthorized encounter content
- **AND** hydration SHALL NOT run

### Requirement: Reuse-first resolution SHALL prefer deterministic monster sources
When an authorized monster is missing locally, runtime hydration SHALL prefer deterministic reuse before AI generation.

#### Scenario: Existing trusted standard monster JSON can be reused
- **WHEN** an authorized missing monster resolves to a trusted reusable standard-monster JSON source
- **THEN** the system SHALL materialize the local module monster file from that reusable source before considering AI generation

#### Scenario: Deterministic reuse unavailable
- **WHEN** an authorized missing monster has no trusted reusable source
- **THEN** the system SHALL use controlled builder hydration as the next fallback
- **AND** failure to hydrate SHALL remain fail-closed

### Requirement: Runtime-authoritative monster hydration SHALL only accept schema-sufficient local authority
Runtime-authoritative monster hydration SHALL preserve existing local monster files as authoritative only when those files remain schema-sufficient for shared hydration acceptance.

#### Scenario: Valid existing local monster file remains authoritative
- **GIVEN** a module-local monster file already exists
- **AND** it contains the minimum required structured fields for hydration acceptance
- **WHEN** runtime-authorized monster hydration evaluates the monster
- **THEN** the helper SHALL preserve the existing file as authoritative
- **AND** SHALL remain backward compatible with current runtime behavior.

#### Scenario: Schema-incomplete existing local file does not block shared recovery
- **GIVEN** a module-local monster file already exists for an authorized monster
- **AND** that file is schema-incomplete for shared hydration acceptance
- **WHEN** runtime-authorized monster hydration evaluates the monster
- **THEN** the helper SHALL NOT stop at the existing file solely because it is present
- **AND** SHALL continue to reusable, bestiary, or controlled generation recovery according to existing precedence rules.


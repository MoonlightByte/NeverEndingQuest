## ADDED Requirements

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

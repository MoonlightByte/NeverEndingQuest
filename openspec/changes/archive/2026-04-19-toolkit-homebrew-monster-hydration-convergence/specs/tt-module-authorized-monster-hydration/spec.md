## MODIFIED Requirements

### Requirement: Module-authorized monsters SHALL be hydratable across builder, finisher, and encounter workflows
Encounter creation and toolkit module convergence workflows SHALL allow a missing monster stat file to be materialized only when that monster can be validated against authored module content.

#### Scenario: Authorized standard monster is missing local stat file
- **WHEN** a packet-built module, finisher run, or `createEncounter` references a monster whose normalized name is authorized by authored content in the active module
- **AND** `modules/<module>/monsters/<normalized_name>.json` does not exist
- **THEN** the system SHALL treat the monster as `authorized_missing`
- **AND** SHALL attempt shared hydration using deterministic reuse, bestiary materialization, or controlled builder generation before failing

#### Scenario: Existing local monster file remains authoritative
- **WHEN** a builder, finisher, readiness, or runtime workflow references a monster whose module-local stat file already exists
- **THEN** the system SHALL use the existing local file without invoking further hydration
- **AND** encounter and toolkit startup behavior SHALL remain backward compatible

#### Scenario: Authorized bespoke monster is missing deterministic sources
- **WHEN** an authorized monster has no reusable deterministic source and no bestiary entry
- **THEN** the system SHALL allow controlled builder hydration for that authorized monster
- **AND** hydration SHALL succeed only when a schema-valid local monster file is created

### Requirement: Runtime authorization SHALL derive from authored module content only
Monster authorization for shared hydration SHALL come from authored module assets, not freeform runtime narration.

#### Scenario: Authored module content authorizes a creature
- **WHEN** a normalized monster identity is present in authored module sources used by the authorization roster
- **THEN** builder, finisher, readiness, and runtime workflows SHALL treat that identity as eligible for hydration if its local file is missing

#### Scenario: Packet-built module without seed file still authorizes authored monster
- **WHEN** `monsters_seed.json` is absent
- **AND** authored area or equivalent builder-owned module content names a monster identity
- **THEN** shared hydration SHALL treat that monster as authorized by authored module content
- **AND** SHALL NOT require seed-file presence as the sole authorization source

#### Scenario: Runtime narration alone does not authorize a creature
- **WHEN** a monster appears only in live model narration or chat history
- **AND** the active module content does not authorize that normalized identity
- **THEN** builder, readiness, finisher, and runtime hydration SHALL reject it as unauthorized encounter content
- **AND** hydration SHALL NOT run

### Requirement: Reuse-first resolution SHALL prefer deterministic monster sources
When an authorized monster is missing locally, shared hydration SHALL prefer deterministic reuse before AI generation.

#### Scenario: Existing trusted standard monster JSON can be reused
- **WHEN** an authorized missing monster resolves to a trusted reusable standard-monster JSON source
- **THEN** the system SHALL materialize the local module monster file from that reusable source before considering bestiary or AI generation

#### Scenario: Bestiary-backed deterministic source is available
- **WHEN** an authorized missing monster has no reusable module-local source
- **AND** the normalized identity resolves in the shipped bestiary data
- **THEN** the system SHALL materialize the local module monster file from that bestiary-backed source before considering AI generation

#### Scenario: Deterministic reuse unavailable
- **WHEN** an authorized missing monster has no trusted reusable source and no bestiary-backed source
- **THEN** the system SHALL use controlled builder hydration as the next fallback
- **AND** failure to hydrate SHALL remain fail-closed

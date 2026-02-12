## ADDED Requirements

### Requirement: All PC creation paths SHALL use one shared completeness audit pipeline
All player-character creation entry points SHALL invoke a shared server-side pipeline that performs canonical normalization, schema validation against `schemas/char_schema.json`, and completeness auditing before writing character files.

#### Scenario: Startup creation uses shared audit
- **WHEN** startup wizard finalizes a newly created character
- **THEN** the shared audit pipeline validates and approves the payload before persistence

#### Scenario: DM interview creation uses shared audit
- **WHEN** Create with DM produces final JSON
- **THEN** the same shared audit pipeline validates and approves the payload before persistence

#### Scenario: Roll Your Own creation uses shared audit
- **WHEN** manual creation submits character data
- **THEN** the same shared audit pipeline validates and approves the payload before persistence

### Requirement: Completeness audit SHALL enforce deterministic error classes and outcomes
The audit pipeline SHALL emit deterministic validation outcomes: `schema_error`, `completeness_error`, or `success`, and SHALL define expected handling for each outcome.

#### Scenario: Schema validation failure
- **WHEN** required fields or types violate schema
- **THEN** result is `schema_error`, save is blocked, and missing/invalid field paths are returned

#### Scenario: Completeness validation failure
- **WHEN** schema passes but critical content is placeholder/empty (for example narrative identity fields)
- **THEN** result is `completeness_error`, save is blocked, and actionable completion requirements are returned

#### Scenario: Successful validation
- **WHEN** schema and completeness checks both pass
- **THEN** result is `success` and character persistence proceeds

### Requirement: Post-create enrichment SHALL preserve mechanical truth
If enrichment is enabled, enrichment SHALL only modify approved narrative fields (for example `backgroundFeature.description`) and SHALL NOT alter mechanical state fields such as HP, AC, abilities, saves, skills, spell slots, or equipment mechanics.

#### Scenario: Background feature enrichment
- **WHEN** a newly validated character has a generic background feature description
- **THEN** enrichment may improve the description while preserving field structure and source attribution

#### Scenario: Mechanical fields remain unchanged
- **WHEN** enrichment runs after validation
- **THEN** mechanical fields remain byte-for-byte equivalent to pre-enrichment values

### Requirement: Sheet and PDF consumers SHALL support readiness audit visibility without breaking existing exports
Character sheet UI and PDF export paths SHALL surface readiness audit warnings for incomplete legacy characters while preserving existing non-breaking export behavior for valid characters.

#### Scenario: Valid character sheet and PDF export
- **WHEN** character data passes readiness audit
- **THEN** UI rendering and PDF export proceed without warnings

#### Scenario: Legacy incomplete character detected
- **WHEN** a pre-existing character fails readiness audit during sheet/PDF request
- **THEN** the system surfaces non-fatal warning context and continues using current defensive defaults unless explicit repair is requested

### Requirement: Backward compatibility invariants SHALL hold for SP and TT runtime behavior
The implementation SHALL preserve single-player startup compatibility and tabletop runtime compatibility, including party-tracker semantics and existing route contracts.

#### Scenario: Single-player mode compatibility
- **WHEN** no additional players are added in startup
- **THEN** startup behavior and resulting party state match existing single-player expectations

#### Scenario: Tabletop mode compatibility
- **WHEN** multiple players are created or added
- **THEN** `partyMembers` and `active_character` remain consistent and no combat/state synchronization regressions are introduced

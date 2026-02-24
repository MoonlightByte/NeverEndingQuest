## Purpose

Define shared, deterministic completeness auditing for PC creation and readiness visibility so creation, sheet rendering, and export paths remain reliable and backward compatible.

## Requirements

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
- **THEN** result is `schema_error`, save is blocked, and missing or invalid field paths are returned

#### Scenario: Completeness validation failure
- **WHEN** schema passes but critical content is placeholder or empty (for example narrative identity fields)
- **THEN** result is `completeness_error`, save is blocked, and actionable completion requirements are returned

#### Scenario: Completeness validation failure includes backstory
- **WHEN** schema passes but critical narrative fields are empty or placeholder (including `backstory`)
- **THEN** result is `completeness_error`, save is blocked, and missing or invalid paths include `backstory`

#### Scenario: Successful validation includes authored backstory
- **WHEN** schema and completeness checks both pass with non-empty `backstory`
- **THEN** result is `success` and character persistence proceeds

### Requirement: Post-create enrichment SHALL preserve mechanical truth

If enrichment is enabled, enrichment SHALL only modify approved narrative fields (for example `backgroundFeature.description`) and SHALL NOT alter mechanical state fields such as HP, AC, abilities, saves, skills, spell slots, or equipment mechanics.

#### Scenario: Background-feature enrichment
- **WHEN** a newly validated character has a generic background-feature description
- **THEN** enrichment may improve the description while preserving field structure and source attribution

#### Scenario: Mechanical fields remain unchanged
- **WHEN** enrichment runs after validation
- **THEN** mechanical fields remain byte-for-byte equivalent to pre-enrichment values

### Requirement: Sheet and PDF consumers SHALL support readiness audit visibility without breaking existing exports

Character sheet UI and PDF export paths SHALL surface readiness-audit warnings for incomplete legacy characters while preserving existing non-breaking export behavior for valid characters.

#### Scenario: Valid character sheet and PDF export
- **WHEN** character data passes readiness audit
- **THEN** UI rendering and PDF export proceed without warnings

#### Scenario: Legacy incomplete character detected
- **WHEN** a pre-existing character fails readiness audit during sheet or PDF request
- **THEN** the system surfaces non-fatal warning context and continues using current defensive defaults unless explicit repair is requested

#### Scenario: Legacy incomplete character missing backstory
- **WHEN** a pre-existing character fails readiness audit due to missing `backstory`
- **THEN** readiness output includes actionable warning context without blocking render or export

#### Scenario: Generic background-feature placeholder failure
- **WHEN** schema passes but `backgroundFeature.name` or `backgroundFeature.description` matches configured generic placeholder values
- **THEN** result is `completeness_error` and returned missing or invalid paths identify the generic placeholder fields

### Requirement: Shared audit pipeline SHALL gate manual edit persistence
Manual Roll Your Own edit persistence SHALL invoke the same canonical normalization and audit pipeline used for creation before writing character files.

#### Scenario: Edit payload passes audit
- **WHEN** merged edit payload satisfies schema and completeness checks
- **THEN** edit persistence proceeds and returns success

#### Scenario: Edit payload fails audit
- **WHEN** merged edit payload fails schema or completeness checks
- **THEN** save is blocked, structured validation errors are returned, and existing character file remains unchanged

### Requirement: Audit-gated edit path SHALL remain deterministic
Manual edit route SHALL remain deterministic and SHALL not invoke LLM-based update flows.

#### Scenario: Edit route handling contract
- **WHEN** Roll Your Own edit submit is processed
- **THEN** the route applies deterministic field mapping and audit gating without calling `updateCharacterInfo`


The implementation SHALL preserve single-player startup compatibility and tabletop runtime compatibility, including party-tracker semantics and existing route contracts.

#### Scenario: Single-player mode compatibility
- **WHEN** no additional players are added in startup
- **THEN** startup behavior and resulting party state match existing single-player expectations

#### Scenario: Tabletop mode compatibility
- **WHEN** multiple players are created or added
- **THEN** `partyMembers` and `active_character` remain consistent and no combat/state synchronization regressions are introduced

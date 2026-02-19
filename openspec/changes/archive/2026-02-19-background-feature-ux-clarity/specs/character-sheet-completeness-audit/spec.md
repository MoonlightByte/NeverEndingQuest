## MODIFIED Requirements

### Requirement: Completeness audit SHALL enforce deterministic error classes and outcomes
The audit pipeline SHALL emit deterministic validation outcomes: `schema_error`, `completeness_error`, or `success`, and SHALL define expected handling for each outcome.

#### Scenario: Schema validation failure
- **WHEN** required fields or types violate schema
- **THEN** result is `schema_error`, save is blocked, and missing/invalid field paths are returned

#### Scenario: Completeness validation failure
- **WHEN** schema passes but critical content is placeholder/empty (for example narrative identity fields)
- **THEN** result is `completeness_error`, save is blocked, and actionable completion requirements are returned

#### Scenario: Generic background-feature placeholder failure
- **WHEN** schema passes but `backgroundFeature.name` or `backgroundFeature.description` matches configured generic placeholder values
- **THEN** result is `completeness_error` and returned missing/invalid paths identify the generic placeholder field(s)

#### Scenario: Successful validation
- **WHEN** schema and completeness checks both pass
- **THEN** result is `success` and character persistence proceeds

### Requirement: Sheet and PDF consumers SHALL support readiness audit visibility without breaking existing exports
Character sheet UI and PDF export paths SHALL surface readiness audit warnings for incomplete legacy characters, including generic background-feature placeholders, while preserving existing non-breaking export behavior for valid characters.

#### Scenario: Valid character sheet and PDF export
- **WHEN** character data passes readiness audit
- **THEN** UI rendering and PDF export proceed without warnings

#### Scenario: Legacy incomplete character detected
- **WHEN** a pre-existing character fails readiness audit during sheet/PDF request
- **THEN** the system surfaces non-fatal warning context and continues using current defensive defaults unless explicit repair is requested

#### Scenario: Generic placeholder detected in legacy character
- **WHEN** a character contains generic background-feature placeholder values during sheet/PDF request
- **THEN** readiness output includes actionable warning context for those fields without blocking render/export

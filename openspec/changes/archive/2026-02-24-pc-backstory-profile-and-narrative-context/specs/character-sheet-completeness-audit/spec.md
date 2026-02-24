## MODIFIED Requirements

### Requirement: Completeness audit SHALL enforce deterministic error classes and outcomes
The audit pipeline SHALL emit deterministic validation outcomes: `schema_error`, `completeness_error`, or `success`, and SHALL define expected handling for each outcome.

#### Scenario: Completeness validation failure includes backstory
- **WHEN** schema passes but critical narrative fields are empty or placeholder (including `backstory`)
- **THEN** result is `completeness_error`, save is blocked, and missing/invalid paths include `backstory`

#### Scenario: Successful validation includes authored backstory
- **WHEN** schema and completeness checks both pass with non-empty `backstory`
- **THEN** result is `success` and character persistence proceeds

### Requirement: Sheet and PDF consumers SHALL surface readiness context for backstory gaps
Character sheet UI and PDF export paths SHALL include non-fatal readiness warnings when `backstory` is missing on legacy characters.

#### Scenario: Legacy incomplete character missing backstory
- **WHEN** a pre-existing character fails readiness audit due to missing `backstory`
- **THEN** readiness output includes actionable warning context without blocking render/export

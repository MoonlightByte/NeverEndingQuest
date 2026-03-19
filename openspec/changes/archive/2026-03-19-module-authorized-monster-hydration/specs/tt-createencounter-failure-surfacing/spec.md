## MODIFIED Requirements

### Requirement: createEncounter failure SHALL be explicit and non-misleading
When encounter generation fails because required monster stat files are missing or because a requested monster is not authorized by module-authored content, the system SHALL provide actionable error feedback and SHALL NOT present misleading combat-start narration.

#### Scenario: Authorized missing monster hydration failure emits actionable system error
- **WHEN** `createEncounter` references a monster that is authorized by authored module content
- **AND** its local stat file is missing
- **AND** reuse-first resolution and hydration both fail
- **THEN** action processing SHALL return `status:error`
- **AND** the error message SHALL identify the failure class as authorized monster hydration failure
- **AND** the error message SHALL include monster/stat-file context when available
- **AND** chat history SHALL include a `[SYSTEM]` error message for operator visibility

#### Scenario: Unauthorized monster rejection emits actionable system error
- **WHEN** `createEncounter` references a monster that is not authorized by authored module content
- **THEN** action processing SHALL return `status:error`
- **AND** the error message SHALL identify the monster as unauthorized encounter content
- **AND** hydration SHALL NOT run for that monster
- **AND** chat history SHALL include a `[SYSTEM]` error message for operator visibility

#### Scenario: Failed createEncounter does not leak combat narration
- **WHEN** a model response includes combat-start narration plus `createEncounter`
- **AND** `createEncounter` fails
- **THEN** combat-flavored narration SHALL NOT be emitted to the user for that failed turn
- **AND** only deterministic failure feedback SHALL be shown

#### Scenario: Successful createEncounter behavior unchanged
- **WHEN** encounter generation succeeds
- **THEN** normal narration and combat-start flow SHALL proceed unchanged
- **AND** single-player and multi-player non-failure paths SHALL remain compatible

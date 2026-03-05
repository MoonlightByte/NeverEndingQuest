## MODIFIED Requirements

### Requirement: createEncounter failure SHALL be explicit and non-misleading

When encounter generation fails because required monster stat files are missing, the system SHALL provide actionable error feedback and SHALL NOT present misleading combat-start narration.

#### Scenario: Missing monster stat file emits actionable system error

- **WHEN** `createEncounter` fails because a referenced monster file is missing
- **THEN** action processing SHALL return `status:error`
- **AND** the error message SHALL include missing monster/stat-file context when available
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

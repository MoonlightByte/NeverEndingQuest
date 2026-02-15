## ADDED Requirements

### Requirement: Combat commitment SHALL fail closed on invalid initialization
When combat commitment is reached, the system SHALL NOT continue narrated combat unless formal encounter initialization succeeds.

#### Scenario: Encounter creation failure during commitment
- **WHEN** combat commitment is detected but encounter creation fails or returns invalid state
- **THEN** the system reports a controlled error
- **AND** no narrated combat continuation is emitted as canonical combat progression

### Requirement: Validation retry exhaustion SHALL not execute invalid response fallback
If combat response validation retries are exhausted, the invalid response SHALL NOT be executed as authoritative game progression.

#### Scenario: Validation retries exhausted
- **WHEN** validation retries exceed configured limit
- **THEN** the system aborts that progression step with a controlled failure path
- **AND** does not process the invalid response through normal action execution

## ADDED Requirements

### Requirement: Retrieval operations SHALL emit structured audit records
The system SHALL support structured retrieval audit logging that captures query scope, candidate count, selected event IDs, score component traces, and latency metrics.

#### Scenario: Timeline retrieval audit emission
- **WHEN** a timeline retrieval request is processed with audit logging enabled
- **THEN** an audit row is recorded with request metadata and ranked result trace details

### Requirement: Retrieval policies MUST be externally representable
The system MUST support policy profile representation in structured JSON so scoring weights and caps can be reviewed and versioned without rewriting retrieval logic.

#### Scenario: Policy profile serialization
- **WHEN** a retrieval policy profile is created or updated
- **THEN** scoring parameters are persisted in structured form with version and timestamp metadata

### Requirement: Controller-oriented policy changes SHALL be rollbackable
The system SHALL support append-only change logging for policy/config updates, including actor, reason, previous value, and rollback reference.

#### Scenario: Policy rollback metadata preserved
- **WHEN** a policy change is reverted
- **THEN** the rollback action references the original change and records actor and timestamp details

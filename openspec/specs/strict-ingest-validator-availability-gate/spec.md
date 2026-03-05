# strict-ingest-validator-availability-gate Specification

## Purpose
TBD - created by archiving change module-validation-bulk-default-targeting. Update Purpose after archive.
## Requirements
### Requirement: Strict Ingest Validator Availability Gate
Strict ingest mode SHALL quarantine modules when schema validator dependencies are unavailable.

#### Scenario: Strict ingest with unavailable validator
- WHEN strict ingest is requested and schema validation cannot execute because validator dependencies are unavailable
- THEN ingest SHALL return `status: quarantined`
- AND it SHALL include explicit `quarantine_reason` indicating validator unavailability
- AND it SHALL not report schema validation as passed.

#### Scenario: Non-strict ingest compatibility
- WHEN non-strict ingest is requested and validator dependencies are unavailable
- THEN ingest MAY continue using compatibility behavior
- AND it SHALL record a clear validation-skipped note for operators.


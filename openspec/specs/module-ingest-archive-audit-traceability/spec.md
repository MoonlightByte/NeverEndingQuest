# module-ingest-archive-audit-traceability Specification

## Purpose
TBD - created by archiving change module-ingest-watch-machine. Update Purpose after archive.
## Requirements
### Requirement: Processed ingest sources MUST be archived with explicit status
Every processed source file MUST be moved from `modules/ingest/` into `modules/ingest/archive/` with a status-bearing archive filename.

#### Scenario: Successful ingest
- **WHEN** a source file ingests and validates successfully
- **THEN** source file is moved to archive with `success` status token in filename

#### Scenario: Quarantined ingest
- **WHEN** strict validation fails for generated module output
- **THEN** source file is moved to archive with `quarantined` status token in filename

#### Scenario: Runtime ingest error
- **WHEN** importer throws exception or returns error state
- **THEN** source file is moved to archive with `error` status token in filename

### Requirement: Archive sidecar MUST provide machine-readable audit details
For each archived source file, the system MUST write a `*.result.json` sidecar containing status, module slug (if any), validation summary, artifacts, and errors.

#### Scenario: Success sidecar
- **WHEN** ingest succeeds
- **THEN** sidecar includes `status=success`, generated artifact list, and validation pass metadata

#### Scenario: Failure sidecar
- **WHEN** ingest is quarantined or errors
- **THEN** sidecar includes `status`, validation or exception errors, and quarantine reason where applicable

### Requirement: Archiving SHALL be non-destructive under filename collisions
Archive operations SHALL preserve all processed inputs even when timestamp/name collisions occur.

#### Scenario: Archive target filename already exists
- **WHEN** computed archive path conflicts with existing file
- **THEN** worker resolves collision with deterministic suffixing and preserves both files

#### Scenario: Repeated ingest of same source filename
- **WHEN** same source filename is processed multiple times
- **THEN** each processing event results in distinct archived file and sidecar pair


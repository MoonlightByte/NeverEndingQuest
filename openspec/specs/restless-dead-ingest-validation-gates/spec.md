# restless-dead-ingest-validation-gates Specification

## Purpose
TBD - created by archiving change night-restless-dead-branching-horror-expansion. Update Purpose after archive.
## Requirements
### Requirement: Ingest Audit Gate Reporting
Expansion workflow SHALL run ingest sidecar audit and report explicit status (PASS/DEGRADED/FAIL).

#### Scenario: Missing sidecar is surfaced explicitly
- **WHEN** sidecar audit is run and sidecar is absent
- **THEN** workflow reports gate status as DEGRADED or FAIL with explicit reason
- **AND** implementation notes capture the unresolved ingest artifact gap

### Requirement: Validation Mode Declaration
Workflow SHALL declare strict vs degraded validation mode based on environment capabilities.

#### Scenario: jsonschema unavailable
- **WHEN** strict validator cannot run due missing `jsonschema`
- **THEN** workflow records degraded mode with explicit fallback checks
- **AND** strict re-run is listed as a pending verification follow-up

### Requirement: Additive Contract Safety
Narrative updates SHALL preserve existing ingest output keys and required schema fields.

#### Scenario: Post-edit contract check
- **WHEN** modified files are validated
- **THEN** required schema fields remain present and valid
- **AND** existing ingest metadata keys remain intact


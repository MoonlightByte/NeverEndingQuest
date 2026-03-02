# ingest-registration-audit-sidecar Specification

## Purpose
TBD - created by archiving change module-ingest-playable-registration. Update Purpose after archive.
## Requirements
### Requirement: Archive sidecar MUST include registration audit details
Every archived ingest result sidecar MUST include registration outcome fields.

#### Scenario: Successful ingest and registration
- **WHEN** ingest succeeds and module is registered
- **THEN** sidecar includes:
  - `registration_attempted = true`
  - `registration_success = true`
  - `registry_module_present = true`
  - `registration_errors = []`

#### Scenario: Registration failure after validation pass
- **WHEN** strict validation passes but registration fails
- **THEN** sidecar includes:
  - `registration_attempted = true`
  - `registration_success = false`
  - `registry_module_present = false`
  - `registration_errors` with failure details
- **AND** status is `quarantined`

### Requirement: Validation failure MUST bypass registration attempt
Registration MUST NOT be attempted when strict validation fails.

#### Scenario: Validation fails
- **WHEN** strict validation reports one or more failed checks
- **THEN** sidecar includes `registration_attempted = false`
- **AND** status remains `quarantined`


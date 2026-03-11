# tt-combat-validation-efficiency-routing Specification

## Purpose
TBD - created by archiving change combat-runtime-authority-and-efficiency. Update Purpose after archive.
## Requirements
### Requirement: Combat validation compression SHALL be threshold-based
Combat validation SHALL only compress assembled validation payloads when the payload exceeds a configured threshold.

#### Scenario: Small combat validation payload uses direct messages
- **WHEN** the assembled combat validation payload remains below the configured threshold
- **THEN** combat validation SHALL skip compression
- **AND** it SHALL send the assembled validation messages directly

#### Scenario: Large combat validation payload is eligible for compression
- **WHEN** the assembled combat validation payload meets or exceeds the configured threshold
- **THEN** combat validation SHALL be allowed to apply compression before the LLM validator call

### Requirement: Combat validation routing SHALL emit deterministic telemetry
Combat validation SHALL emit deterministic routing telemetry for payload size and compression decisions.

#### Scenario: Compression telemetry recorded
- **WHEN** combat validation assembles a payload for validation
- **THEN** it SHALL record a deterministic pre-compression payload-size value
- **AND** it SHALL record a deterministic compression decision reason code


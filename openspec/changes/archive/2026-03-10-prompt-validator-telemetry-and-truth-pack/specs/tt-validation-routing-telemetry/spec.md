## ADDED Requirements

### Requirement: Validation routing SHALL expose deterministic telemetry
The validation pipeline SHALL expose deterministic telemetry for skip and compression routing outcomes.

#### Scenario: Skip telemetry emitted
- **WHEN** validation routing evaluates whether to skip the LLM validator
- **THEN** it SHALL record a deterministic skip decision flag and a skip reason code

#### Scenario: Compression telemetry emitted
- **WHEN** validation routing evaluates whether to compress validator context
- **THEN** it SHALL record whether compression was used, why, and the pre-compression payload size

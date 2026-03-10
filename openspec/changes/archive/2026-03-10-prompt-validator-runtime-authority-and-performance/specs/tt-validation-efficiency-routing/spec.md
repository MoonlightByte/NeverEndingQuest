## ADDED Requirements

### Requirement: Validation compression SHALL be threshold-based
Validation compression SHALL only run when the assembled validation payload exceeds a configured threshold.

#### Scenario: Small validation payload
- **WHEN** validation context remains below the configured threshold
- **THEN** validation SHALL skip compression and use the assembled messages directly

#### Scenario: Large validation payload
- **WHEN** validation context exceeds the configured threshold
- **THEN** validation MAY apply compression before the LLM validator call

### Requirement: Low-risk deterministic-safe turns SHALL have an eligible skip path
The validation pipeline SHALL support skipping the LLM validator for conservative low-risk turns when deterministic checks pass.

#### Scenario: Low-risk turn skip
- **WHEN** the response has only low-risk actions and deterministic checks pass
- **THEN** the pipeline MAY return success without calling the LLM validator

#### Scenario: High-risk turn still validated
- **WHEN** the response touches high-risk actions or semantics
- **THEN** the pipeline SHALL continue to use the LLM validator

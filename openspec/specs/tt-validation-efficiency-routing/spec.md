# tt-validation-efficiency-routing Specification

## Purpose
TBD - created by archiving change prompt-validator-runtime-authority-and-performance. Update Purpose after archive.
## Requirements
### Requirement: Validation compression SHALL be threshold-based
Validation compression SHALL only run when the assembled validation payload exceeds a configured threshold.

#### Scenario: Small validation payload
- **WHEN** validation context remains below the configured threshold
- **THEN** validation SHALL skip compression and use the assembled messages directly

#### Scenario: Large validation payload
- **WHEN** validation context exceeds the configured threshold
- **THEN** validation MAY apply compression before the LLM validator call

### Requirement: Low-risk deterministic-safe turns SHALL have an eligible skip path

The validation pipeline SHALL support skipping or narrowing LLM validation for conservative low-risk turns when deterministic checks pass, including reconcile-first soft-state turns that contain no remaining unreconciled high-risk behavior.

#### Scenario: Reconciled soft-state only turn
- **WHEN** the response contains only deterministic/reconciled travel or NPC soft-state actions
- **AND** no unreconciled high-risk action remains
- **THEN** the pipeline MAY skip or narrow the LLM validator path using deterministic routing rules

#### Scenario: Mixed reconciled and unreconciled turn still reviewed
- **WHEN** a response contains both reconciled soft-state updates and unrelated unreconciled high-risk actions
- **THEN** the pipeline SHALL continue to use the LLM validator for the unreconciled portion


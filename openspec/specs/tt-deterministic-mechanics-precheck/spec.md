# tt-deterministic-mechanics-precheck Specification

## Purpose
TBD - created by archiving change prompt-validator-deterministic-mechanics-precheck. Update Purpose after archive.
## Requirements
### Requirement: Deterministic mechanics precheck SHALL run before LLM validation
The validation pipeline SHALL perform deterministic mechanics checks for covered explicit contradictions before sending the response to the LLM validator.

#### Scenario: Precheck invocation ordering
- **WHEN** `validate_ai_response()` validates an assistant response
- **THEN** deterministic mechanics precheck SHALL run after JSON normalization
- **AND** it SHALL run before the LLM validation API call

### Requirement: Explicit HP contradictions SHALL fail closed
Deterministic validation SHALL reject parseable HP transitions that exceed valid bounds.

#### Scenario: HP above maximum rejected
- **WHEN** `updateCharacterInfo.changes` explicitly indicates a target HP greater than character `maxHitPoints`
- **THEN** validation SHALL fail before LLM validation with a deterministic reason

#### Scenario: HP below zero rejected
- **WHEN** `updateCharacterInfo.changes` explicitly indicates a negative target HP
- **THEN** validation SHALL fail before LLM validation with a deterministic reason

### Requirement: Explicit spell-slot ratio contradictions SHALL fail closed
Deterministic validation SHALL reject parseable spell-slot `current/max` contradictions.

#### Scenario: Current slots above max rejected
- **WHEN** `updateCharacterInfo.changes` explicitly states slot ratio with `current > max`
- **THEN** validation SHALL fail before LLM validation with a deterministic reason

### Requirement: Explicit over-removal from known inventory SHALL fail closed
Deterministic validation SHALL reject parseable item removals that exceed known tracked quantities when deterministic item matching succeeds.

#### Scenario: Removal exceeds known quantity
- **WHEN** `updateCharacterInfo.changes` explicitly removes quantity `N` of a matched tracked item and `N` exceeds known quantity
- **THEN** validation SHALL fail before LLM validation with a deterministic reason

### Requirement: Ambiguous or unparseable mechanics text SHALL fail open
The deterministic precheck SHALL not block responses solely due parser uncertainty.

#### Scenario: Unparseable change text
- **WHEN** `updateCharacterInfo.changes` does not contain parseable covered patterns
- **THEN** deterministic precheck SHALL pass and defer to existing validation flow

### Requirement: Deterministic mechanics precheck SHALL cover additional explicit contradiction classes
The deterministic mechanics precheck SHALL expand beyond its initial HP, slot-ratio, and inventory-removal checks to cover additional explicit contradiction classes while preserving fail-open behavior for ambiguity.

#### Scenario: Ambiguous mechanics text still passes through
- **WHEN** a new guard domain cannot be evaluated deterministically from explicit parseable text or known state
- **THEN** the deterministic precheck SHALL pass and defer to the existing validation flow


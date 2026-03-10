## ADDED Requirements

### Requirement: Explicit spell-slot legality contradictions SHALL fail closed
Deterministic precheck SHALL reject explicit spell-slot contradictions before LLM validation.

#### Scenario: Cantrip incorrectly consumes a slot
- **WHEN** `updateCharacterInfo.changes` explicitly states that a cantrip consumed a spell slot
- **THEN** deterministic precheck SHALL fail before LLM validation with a deterministic reason

#### Scenario: Explicit slot spend would underflow known slots
- **WHEN** `updateCharacterInfo.changes` explicitly spends a known spell slot level beyond the character's available tracked slots
- **THEN** deterministic precheck SHALL fail before LLM validation with a deterministic reason

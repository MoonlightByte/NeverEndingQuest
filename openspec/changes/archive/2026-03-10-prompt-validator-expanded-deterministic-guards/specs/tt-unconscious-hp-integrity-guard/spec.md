## ADDED Requirements

### Requirement: Explicit unconscious-vs-HP contradictions SHALL fail closed
Deterministic precheck SHALL reject explicit mechanical claims that place a character above 0 HP while also explicitly marking them unconscious.

#### Scenario: Above-zero HP plus unconscious rejected
- **WHEN** `updateCharacterInfo.changes` explicitly indicates an HP total above 0 and also explicitly says the character is unconscious
- **THEN** deterministic precheck SHALL fail before LLM validation with a deterministic reason

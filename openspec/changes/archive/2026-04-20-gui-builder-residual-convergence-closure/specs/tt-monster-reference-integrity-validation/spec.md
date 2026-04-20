## ADDED Requirements

### Requirement: Reference-integrity failures SHALL remain consumable by residual closure repair

Validator reference-integrity outputs SHALL remain precise enough for downstream residual closure to derive deterministic monster targets.

#### Scenario: Validator output exposes expected file path deterministically

- **WHEN** reference-integrity validation fails for a missing monster file
- **THEN** the validator output SHALL include the expected normalized monster file path or equivalent deterministic target
- **AND** downstream residual closure SHALL be able to derive a canonical monster identity from that output without guessing

#### Scenario: Ambiguous reference target remains fail-closed

- **WHEN** validator output cannot be mapped back to a single canonical monster identity safely
- **THEN** residual closure SHALL classify the target as unresolved
- **AND** SHALL NOT invent or guess a replacement monster file

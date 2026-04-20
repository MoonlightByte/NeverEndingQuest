## ADDED Requirements

### Requirement: Validator-visible unresolved monster paths SHALL remain repair-targetable

Reference-integrity validation output SHALL remain specific enough for deterministic repair to reconcile the exact expected monster path without ambiguous identity loss.

#### Scenario: Expected monster path drives reconciliation

- **WHEN** `reference_integrity` reports an unresolved path such as `expected monsters/echoes_of_the_party.json`
- **THEN** deterministic repair SHALL be able to derive that exact target slug from validator output
- **AND** reconcile it against authored structured monster evidence in the module

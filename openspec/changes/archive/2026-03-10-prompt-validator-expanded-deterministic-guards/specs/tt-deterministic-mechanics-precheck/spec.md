## ADDED Requirements

### Requirement: Deterministic mechanics precheck SHALL cover additional explicit contradiction classes
The deterministic mechanics precheck SHALL expand beyond its initial HP, slot-ratio, and inventory-removal checks to cover additional explicit contradiction classes while preserving fail-open behavior for ambiguity.

#### Scenario: Ambiguous mechanics text still passes through
- **WHEN** a new guard domain cannot be evaluated deterministically from explicit parseable text or known state
- **THEN** the deterministic precheck SHALL pass and defer to the existing validation flow

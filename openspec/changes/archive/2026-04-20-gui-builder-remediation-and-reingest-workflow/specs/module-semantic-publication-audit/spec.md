# module-semantic-publication-audit Specification Delta

## ADDED Requirements

### Requirement: Semantic audit SHALL distinguish blocking contradictions from warning-only or tooling-debt degradation
The semantic publication audit SHALL preserve a strict distinction between blocking semantic contradictions and degradation caused only by warnings or tooling fixture debt.

#### Scenario: Warning-only semantic degradation remains non-blocking to contradiction classification
- **GIVEN** the semantic audit produces warnings only
- **AND** no blocking semantic findings are present
- **WHEN** the audit result is emitted
- **THEN** it SHALL report a non-blocking degraded state
- **AND** SHALL NOT classify the module as having semantic blocking contradictions.

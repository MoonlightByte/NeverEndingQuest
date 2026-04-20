# module-readiness-continuity-gate Specification Delta

## ADDED Requirements

### Requirement: Toolkit-source readiness SHALL support same-run toolkit provenance validation
Toolkit-source readiness validation SHALL support the current toolkit finisher run satisfying toolkit provenance without weakening watcher-source sidecar enforcement.

#### Scenario: Toolkit current-run provenance passes readiness
- **GIVEN** readiness is running for `source="toolkit"`
- **AND** the current finisher run has provided valid toolkit provenance for the requested module
- **WHEN** readiness evaluates provenance
- **THEN** the provenance gate SHALL pass
- **AND** SHALL NOT require a previously completed historical toolkit report.

#### Scenario: Watcher-source sidecar enforcement remains unchanged
- **GIVEN** readiness is running for `source="watcher"`
- **WHEN** ingest sidecar provenance is missing
- **THEN** readiness SHALL fail closed for watcher provenance
- **AND** SHALL NOT treat toolkit provenance as a substitute.

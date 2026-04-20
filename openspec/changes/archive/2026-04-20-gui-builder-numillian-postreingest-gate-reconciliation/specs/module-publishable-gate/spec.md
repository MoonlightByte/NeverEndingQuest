# module-publishable-gate Specification Delta

## ADDED Requirements

### Requirement: Publishability output SHALL preserve explicit debt classes for structurally valid toolkit modules
Publishability reporting SHALL preserve explicit residual debt classes when a toolkit-built module is structurally valid but still blocked by release-facing media debt or explicitly deferred semantic ambiguity debt.

#### Scenario: Structurally valid toolkit module remains not publishable for explicit residual debt
- **GIVEN** a toolkit-built module passes structural validation and readiness checks required for its declared source
- **AND** publishability still fails because combat-valid monster base media is missing or a semantic issue is explicitly classified as deferred Phase 2 ambiguity debt
- **WHEN** publishability output is emitted
- **THEN** the report SHALL preserve those residual debt classes explicitly
- **AND** SHALL keep the result distinguishable from structural readiness failure

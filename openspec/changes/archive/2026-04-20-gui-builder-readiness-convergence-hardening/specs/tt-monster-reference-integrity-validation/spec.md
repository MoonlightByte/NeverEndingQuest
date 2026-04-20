## ADDED Requirements

### Requirement: Reference-integrity failures SHALL support deterministic convergence repair

Monster reference-integrity failures MUST remain consumable by deterministic repair and convergence-classification workflows.

#### Scenario: Missing monster file is repair-targeted before final classification
- **GIVEN** validation reports an unresolved module monster reference
- **WHEN** readiness convergence remediation runs
- **THEN** the workflow SHALL attempt deterministic monster closure before final failure classification
- **AND** any remaining failure SHALL preserve area/location context and expected file path in the residual blocker report

#### Scenario: Unresolved reference survives deterministic closure attempt
- **GIVEN** convergence remediation attempted deterministic closure for a missing monster file
- **AND** the reference still cannot be resolved safely
- **WHEN** the workflow stops
- **THEN** the result SHALL be classified as residual monster-reference debt
- **AND** readiness SHALL remain failed

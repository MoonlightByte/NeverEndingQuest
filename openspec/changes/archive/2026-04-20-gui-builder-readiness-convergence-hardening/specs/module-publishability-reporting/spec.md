## ADDED Requirements

### Requirement: Reporting SHALL expose readiness convergence outcomes distinctly

Readiness and publishability reports SHALL surface convergence outcomes separately from final ready/publishable status.

#### Scenario: Fixed-point non-convergence is reported distinctly
- **GIVEN** a readiness workflow stops because the blocker signature is unchanged across consecutive passes
- **WHEN** JSON reporting is emitted
- **THEN** the report SHALL include a distinct convergence outcome such as `fixed_point_non_convergence` or equivalent
- **AND** it SHALL NOT collapse that state into a generic readiness failure without classification

#### Scenario: Residual blocker classes are visible in report artifacts
- **GIVEN** a canary or toolkit readiness run ends with unresolved blockers
- **WHEN** the report artifact is written
- **THEN** the artifact SHALL include the residual blocker classes
- **AND** operators SHALL be able to distinguish repair-coverage gaps from content debt

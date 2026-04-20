# module-publishable-gate Specification Delta

## ADDED Requirements

### Requirement: Publishability SHALL fail on semantic blocking findings, not warning-only semantic degradation
The publishable gate SHALL fail when semantic publication layers produce blocking findings, but warning-only or tooling-debt degradation alone SHALL NOT be treated as an equivalent hard semantic blocker.

#### Scenario: Ready module with warning-only semantic degradation remains distinguishable from blocking semantic failure
- **GIVEN** readiness passes
- **AND** semantic publication layers report warnings or tooling debt only
- **AND** no semantic blocking findings are present
- **WHEN** the publishable gate computes final status
- **THEN** it SHALL preserve a status distinct from blocking semantic failure
- **AND** SHALL NOT report the module as blocked by semantic contradiction.

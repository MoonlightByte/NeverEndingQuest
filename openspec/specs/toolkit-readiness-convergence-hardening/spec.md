# toolkit-readiness-convergence-hardening Specification

## Purpose
TBD - created by archiving change gui-builder-readiness-convergence-hardening. Update Purpose after archive.
## Requirements
### Requirement: Toolkit readiness repair SHALL stop on fixed-point blocker sets

Toolkit readiness repair MUST detect when consecutive validation passes produce the same normalized blocker signature and MUST stop with explicit fixed-point classification instead of continuing to spend repair budget.

#### Scenario: Consecutive passes produce identical blocker signatures
- **GIVEN** toolkit readiness has already run one deterministic repair pass
- **AND** the next validation pass yields the same normalized blocker signature
- **WHEN** convergence evaluation runs
- **THEN** the workflow SHALL stop
- **AND** the result SHALL be classified as fixed-point non-convergence
- **AND** the workflow SHALL NOT continue retrying identical blockers solely because budget remains

### Requirement: Toolkit readiness reporting SHALL classify residual blocker families

Toolkit readiness reports MUST classify unresolved blocker families separately from generic budget exhaustion.

#### Scenario: Residual blockers remain after fixed-point detection
- **GIVEN** a toolkit readiness run stops on fixed-point non-convergence
- **WHEN** the JSON report is emitted
- **THEN** the report SHALL include `residual_blocker_classes` or equivalent
- **AND** the classes SHALL identify each unresolved validator family distinctly

### Requirement: Numillian canary SHALL be used to verify convergence hardening

The repository SHALL use `The_Hidden_City_of_Numillian` as a readiness convergence canary for this slice.

#### Scenario: Numillian rerun validates convergence improvements
- **GIVEN** convergence hardening has been implemented
- **WHEN** the Numillian readiness canary rerun executes
- **THEN** the workflow SHALL either advance beyond the previous schema-gate fixed point or classify the remaining blockers as residual content debt
- **AND** it SHALL NOT terminate on unchanged-blocker budget exhaustion without classification


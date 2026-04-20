## ADDED Requirements

### Requirement: Deterministic remediation SHALL repair uniquely provable finale prerequisites

When a finale or conclusion beat lacks explicit prerequisite gating but the upstream dependency chain is uniquely provable, remediation SHALL insert the missing prerequisite deterministically.

#### Scenario: Finale prerequisite is uniquely provable
- **GIVEN** validation reports a finale or conclusion beat missing an explicit prerequisite gate
- **AND** one upstream dependency is uniquely implied by the authored progression chain
- **WHEN** deterministic remediation runs
- **THEN** the missing prerequisite SHALL be added
- **AND** revalidation SHALL evaluate the repaired plot graph

#### Scenario: Finale prerequisite remains ambiguous
- **GIVEN** validation reports a missing finale prerequisite gate
- **AND** multiple upstream dependencies could satisfy the authored intent
- **WHEN** deterministic remediation runs
- **THEN** it SHALL NOT guess a prerequisite
- **AND** the result SHALL be classified as residual plot-gating debt

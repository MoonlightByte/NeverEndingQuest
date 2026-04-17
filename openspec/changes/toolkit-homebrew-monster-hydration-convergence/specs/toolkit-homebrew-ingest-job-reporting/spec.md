## ADDED Requirements

### Requirement: Toolkit job reporting SHALL expose monster hydration convergence outcomes
Toolkit job reporting SHALL distinguish successful monster hydration from unresolved or unauthorized monster blockers without requiring operators to inspect raw stderr output.

#### Scenario: Toolkit reports winning hydration mode
- **WHEN** a toolkit build, readiness repair, or finisher stage hydrates a missing monster reference
- **THEN** the toolkit SHALL expose the winning hydration mode such as `existing`, `reuse`, `bestiary`, or `generated`
- **AND** SHALL include the normalized monster identity in structured stage reporting

#### Scenario: Toolkit reports blocking hydration failure class
- **WHEN** monster hydration fails or is rejected during toolkit build, readiness, or finishing
- **THEN** the toolkit SHALL surface a stable failure class such as `unauthorized_monster_reference`, `authorized_monster_hydration_failed`, or `provider_unavailable`
- **AND** SHALL preserve enough structured detail for the operator to understand why readiness or finishing remained blocked

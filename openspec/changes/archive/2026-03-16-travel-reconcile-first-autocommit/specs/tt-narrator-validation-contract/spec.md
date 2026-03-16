## ADDED Requirements

### Requirement: Travel-intent validation SHALL prefer reconciliation over rejection when movement is legal
For turns classified as travel intent, narrator validation SHALL prefer runtime reconciliation over missing-action rejection when narrated movement is legal, topology-safe, and safely resolvable.

#### Scenario: Legal narrated movement without explicit travel action
- **WHEN** a turn is classified as travel intent
- **AND** narrated movement is legal and safely resolvable
- **AND** explicit `transitionLocation` is missing
- **THEN** validation SHALL allow runtime travel reconciliation to proceed
- **AND** the turn SHALL NOT fail solely for missing explicit travel action

#### Scenario: Illegal travel remains blocking
- **WHEN** a turn is classified as travel intent
- **AND** narrated movement is topology-illegal or unsafe to resolve
- **THEN** validation SHALL continue to block the travel commit
- **AND** runtime SHALL NOT treat reconcile-first behavior as a bypass for impossible movement

#### Scenario: Ambiguous travel requests clarification instead of wrong commit
- **WHEN** a turn is classified as travel intent
- **AND** narrated movement cannot be resolved safely to one destination or one progress interpretation
- **THEN** validation SHALL preserve safe current truth or request clarification
- **AND** SHALL NOT require an arbitrary exact destination commit

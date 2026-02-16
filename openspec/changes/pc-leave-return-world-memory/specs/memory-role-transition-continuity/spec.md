## MODIFIED Requirements

### Requirement: Role transitions SHALL preserve canonical identity
The system SHALL represent retirement, return, and PC/NPC role changes as role-timeline updates on the same canonical entity identity, and retirement/reactivation MUST update canonical entity retirement state without creating duplicate entities.

#### Scenario: Retirement followed by return
- **WHEN** an entity retires and later returns to active party participation
- **THEN** role history records both transitions while keeping one canonical entity identifier

#### Scenario: Canonical retirement-state toggle
- **WHEN** a retirement transition is persisted and later a return transition is persisted for the same entity
- **THEN** the canonical entity record reflects retired state after leave and active state after return without changing entity identifier

## ADDED Requirements

### Requirement: Gameplay leave/return paths MUST persist transition milestones as first-class memory events
The system MUST write retirement and return lifecycle events from gameplay party-management paths into long-term memory as `role_transition` events with high continuity weight.

#### Scenario: Retirement transition event persisted from retire endpoint
- **WHEN** a retire-character operation succeeds
- **THEN** a `role_transition` memory event is persisted and linked to the departing entity

#### Scenario: Return transition event persisted from add-existing endpoint
- **WHEN** a previously retired character is re-added through Add Existing
- **THEN** a `role_transition` memory event is persisted and linked to the returning entity

### Requirement: Transition memory persistence MUST be non-destructive to historical links
Retirement and return persistence MUST NOT delete prior memory events or links for the transitioning entity.

#### Scenario: Prior relationship memory retained after retirement
- **WHEN** an entity with existing linked memory events is retired
- **THEN** previously linked events remain retrievable for that entity after retirement

### Requirement: Transition events SHALL include witness continuity links
Retirement and return events SHALL include witness links for relevant party participants to support continuity narration retrieval.

#### Scenario: Retirement event linked to witnesses
- **WHEN** a retirement event is created during party operation
- **THEN** the event contains witness links for relevant remaining party entities available in request-time context

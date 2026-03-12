## Purpose

Define identity continuity and milestone retrieval behavior for PC/NPC role transitions across time.

## Requirements

### Requirement: Role transitions SHALL preserve canonical identity
The system SHALL represent retirement, return, and PC/NPC role changes as role-timeline updates on the same canonical entity identity.

#### Scenario: Retirement followed by return
- **WHEN** an entity retires and later returns to active party participation
- **THEN** role history records both transitions while keeping one canonical entity identifier

### Requirement: Retirement and return memories MUST be retrievable as first-class milestones
The system MUST support direct retrieval of retirement/return events for an entity using deterministic ranking.

#### Scenario: Retrieve retirement/return timeline
- **WHEN** a retirement-return retrieval query is executed for an entity with both event types
- **THEN** both retirement and return events are present in ranked results

### Requirement: Active-party relevance SHALL boost transition memory visibility
The system SHALL boost priority for transition memories involving active party entities to support coherent reunion and continuity narration.

#### Scenario: Active PC transition event priority
- **WHEN** a role-transition event links the current active character
- **THEN** the event receives active-party priority weighting in retrieval

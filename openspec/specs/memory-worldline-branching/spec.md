## Purpose

Define requirements for Many Worlds worldline lineage tracking across save/restore operations, enabling timeline ancestry and divergent replay branching.

## Requirements

### Requirement: Save metadata SHALL include worldline lineage fields
The system SHALL persist lineage fields in save metadata to describe timeline ancestry across restores and divergent replays.

#### Scenario: Save metadata includes lineage
- **WHEN** a save is created
- **THEN** save metadata includes `save_id` and `worldline_id`
- **AND** parent/fork lineage fields are populated according to current timeline context

### Requirement: First save after restore SHALL fork a new worldline
The system SHALL create a new worldline identity on the first save created after any restore operation.

#### Scenario: Restore then save creates branch
- **WHEN** a save is restored and the next save is created
- **THEN** the new save has a different `worldline_id` from the restored save
- **AND** parent linkage points to the restored save lineage

### Requirement: Consecutive saves without restore SHALL remain in same worldline
The system SHALL keep subsequent saves in the active worldline until another restore occurs.

#### Scenario: Save without intervening restore
- **WHEN** two saves are created sequentially without restore between them
- **THEN** both saves share the same `worldline_id`

### Requirement: Restore context SHALL persist enough lineage state for deterministic next-save branching
The system SHALL persist restore context so branch metadata generation is deterministic and does not depend on transient process memory.

#### Scenario: Process restart after restore
- **WHEN** restore completes and process restarts before the next save
- **THEN** the next save still applies fork-on-first-save-after-restore semantics correctly

## ADDED Requirements

### Requirement: Diary draft SHALL refresh on Start Game when source history is stale
The system SHALL run a draft diary freshness check during Start Game and create or update one draft diary entry only when source history advanced since the last draft checkpoint.

#### Scenario: Stale history at game start
- **WHEN** the user starts the game and memory source events exceed the last draft checkpoint
- **THEN** the system updates the draft diary entry and records a new draft checkpoint without blocking game start

#### Scenario: No source changes at game start
- **WHEN** the user starts the game and no source events were added since the last draft checkpoint
- **THEN** no new draft diary entry is created and no duplicate draft is emitted

### Requirement: Save confirmation MUST create canonical diary entries idempotently by save_id
The system MUST create at most one confirmed diary entry per `save_id` and treat the save boundary as canonical diary confirmation.

#### Scenario: First confirmation for save_id
- **WHEN** a save operation completes with a new `save_id`
- **THEN** one confirmed diary entry is persisted and associated with that `save_id`

#### Scenario: Duplicate save_id confirmation attempt
- **WHEN** confirmation logic is re-invoked with an already confirmed `save_id`
- **THEN** the system does not create a duplicate confirmed entry

### Requirement: Diary generation failures SHALL NOT block Start Game or Save flows
Diary generation and checkpoint writes SHALL be failure-isolated so critical gameplay operations continue when diary generation errors occur.

#### Scenario: Draft generation failure on start
- **WHEN** draft generation throws an exception during Start Game
- **THEN** Start Game still succeeds and the failure is logged

#### Scenario: Confirmed generation failure on save
- **WHEN** confirmed diary generation throws an exception during save
- **THEN** save succeeds and the failure is logged without save rollback

### Requirement: Diary entries MUST be ordered by game-world time
The system MUST store and query diary entries using normalized game-world time ordering rather than wall-clock insertion order.

#### Scenario: Display ordering with out-of-order writes
- **WHEN** entries are inserted at different wall-clock times but represent game-world times out of write order
- **THEN** list queries return entries sorted by game-world order

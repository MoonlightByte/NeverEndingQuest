# journal-diary-dual-checkpoint Specification

## Purpose
TBD - created by archiving change journal-diary-storyteller-mvp. Update Purpose after archive.
## Requirements
### Requirement: Start Game SHALL maintain one active draft diary checkpoint
The system SHALL evaluate diary freshness on Start Game and SHALL create or refresh at most one active `draft` diary entry when new source history exists beyond the last draft checkpoint. Draft generation SHALL be non-blocking and SHALL not prevent the game from starting.

#### Scenario: Draft is refreshed when source history advanced
- **WHEN** Start Game runs and new eligible source events exist after the last draft checkpoint
- **THEN** the system SHALL create or update exactly one active `draft` diary entry using the new source window

#### Scenario: Draft is not duplicated when no new source history exists
- **WHEN** Start Game runs and no eligible source events exist after the last draft checkpoint
- **THEN** the system SHALL leave the current draft state unchanged and SHALL NOT create an additional draft row

#### Scenario: Draft generation fails without blocking game start
- **WHEN** Start Game triggers draft refresh and diary generation raises an exception or returns an error
- **THEN** the system SHALL still start the game successfully and SHALL record the diary outcome as degraded rather than failing the start flow

### Requirement: Save SHALL create idempotent confirmed diary checkpoints
The system SHALL generate a `confirmed` diary entry during save creation and SHALL bind that entry to the active `save_id`. Confirmed diary creation SHALL be idempotent for the same `save_id` and SHALL not produce duplicate confirmed rows.

#### Scenario: Save creates one confirmed diary entry
- **WHEN** a save completes successfully and no confirmed diary row exists for that `save_id`
- **THEN** the system SHALL create exactly one confirmed diary entry linked to that `save_id`

#### Scenario: Reprocessing the same save does not duplicate canon entries
- **WHEN** the system attempts confirmed diary creation for a `save_id` that already has a confirmed diary row
- **THEN** the system SHALL reuse the existing confirmed checkpoint behavior and SHALL NOT create a second confirmed row

#### Scenario: Diary generation failure does not fail save
- **WHEN** confirmed diary creation fails during save processing
- **THEN** the save operation SHALL still succeed and the diary result SHALL be surfaced as degraded metadata rather than a save failure

### Requirement: Explicit Exit SHALL auto-confirm unsaved diary progress
The explicit GUI Exit path SHALL create an idempotent `confirmed` diary checkpoint when eligible source history exists beyond the last confirmed checkpoint, even if the player did not manually save. This checkpoint SHALL be lighter-weight than a save snapshot and SHALL not create save-game artifacts by itself.

#### Scenario: Exit creates one confirmed diary entry when unsaved progress exists
- **WHEN** the player uses explicit GUI Exit and new eligible source events exist after the last confirmed diary checkpoint
- **THEN** the system SHALL create exactly one new confirmed diary entry for that unsaved progress window

#### Scenario: Repeated exit processing does not duplicate canon entries
- **WHEN** the system reprocesses the same explicit Exit checkpoint window because of repeated clicks or shutdown retries
- **THEN** it SHALL reuse the existing confirmed checkpoint behavior and SHALL NOT create duplicate confirmed diary rows

#### Scenario: Exit with no new progress does not create extra confirmed rows
- **WHEN** the player uses explicit GUI Exit and no eligible source events exist after the last confirmed diary checkpoint
- **THEN** the system SHALL leave confirmed diary state unchanged and SHALL NOT create an additional confirmed row

#### Scenario: Diary confirmation failure does not block exit
- **WHEN** explicit Exit triggers diary confirmation and diary generation raises an exception or returns an error
- **THEN** the system SHALL still complete the exit flow and SHALL surface the diary result as degraded rather than failing shutdown

### Requirement: Draft and confirmed diary state SHALL remain segregated
The diary system SHALL preserve a strict boundary between unsaved draft content and confirmed save-bound canon content.

#### Scenario: Only one draft row may remain active
- **WHEN** draft refresh runs repeatedly across multiple Start Game events
- **THEN** the system SHALL keep at most one active draft row and SHALL supersede or update older draft state rather than accumulating multiple active drafts

#### Scenario: Confirmed timeline excludes draft rows
- **WHEN** a caller requests confirmed diary history for story compilation or canonical timeline display
- **THEN** the system SHALL return confirmed rows only and SHALL exclude draft rows from that canonical result set

#### Scenario: Exit auto-confirm clears superseded draft state
- **WHEN** explicit Exit successfully confirms a diary checkpoint from the active draft window
- **THEN** the system SHALL clear or supersede the active draft row so the next Start Game begins from a fresh draft boundary


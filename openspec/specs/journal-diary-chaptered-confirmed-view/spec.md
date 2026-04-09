# journal-diary-chaptered-confirmed-view Specification

## Purpose
TBD - created by archiving change journal-diary-chaptered-confirmed-chronicle. Update Purpose after archive.
## Requirements
### Requirement: Confirmed Diary SHALL rebuild from ordered journal chronology
The system SHALL build confirmed Diary rebuilds from `journal.json.entries` in source order. Confirmed Diary rebuild sequencing MUST treat journal entry order as authoritative chronology for chapter construction rather than reordering entries from broader memory DB history.

#### Scenario: Rebuild uses journal entry order
- **WHEN** a confirmed Diary rebuild is executed against a campaign with ordered `journal.json.entries`
- **THEN** the rebuilt confirmed Diary rows SHALL appear in the same narrative order as the journal entries used to build them

#### Scenario: Rebuild does not require checkpoint-window history as primary source
- **WHEN** `journal.json.entries` are available for a confirmed Diary rebuild
- **THEN** the rebuild SHALL derive chapter content from those journal entries instead of using checkpoint-window DB history as the primary narrative source

### Requirement: Confirmed Diary SHALL group journal entries into chapter blocks
The system SHALL group adjacent journal entries into chapter blocks for confirmed Diary rebuilds. Grouping MUST collapse duplicate or near-duplicate retellings of the same beat while preserving distinct scene progression when the journal sequence clearly advances.

#### Scenario: Exact duplicate journal variants collapse
- **WHEN** adjacent journal entries describe the same beat with the same effective time and location
- **THEN** the confirmed Diary rebuild SHALL collapse them into a single chapter block

#### Scenario: Distinct scene progression is preserved
- **WHEN** adjacent journal entries occur at the same location but clearly represent separate scene progression
- **THEN** the confirmed Diary rebuild SHALL keep them as separate chapter blocks

### Requirement: Draft Diary SHALL remain separate from confirmed chapter rebuilds
The system SHALL keep draft Diary generation on its existing checkpoint/live-session path. Confirmed journal-chapter rebuild behavior MUST NOT replace or disable draft Diary hooks.

#### Scenario: Confirmed rebuild leaves draft model unchanged
- **WHEN** a confirmed Diary rebuild is performed
- **THEN** draft Diary behavior SHALL remain checkpoint/live-session based rather than converting to journal-chapter rebuild mode

### Requirement: Confirmed Diary SHALL preserve explicit world-line metadata
Each confirmed Diary chapter row SHALL preserve explicit world date/time and location metadata suitable for Journal modal rendering. Confirmed rebuilt rows MUST remain title-free in the UI while still exposing metadata for display.

#### Scenario: Confirmed chapter row carries display metadata
- **WHEN** a confirmed Diary chapter row is rebuilt
- **THEN** the row SHALL retain world date/time and primary location metadata for rendering in the Journal modal

#### Scenario: Confirmed rows render without fixed chronicle title
- **WHEN** the Journal modal renders confirmed Diary entries
- **THEN** it SHALL render the metadata and body without a fixed repeated title label such as `Confirmed Chronicle`


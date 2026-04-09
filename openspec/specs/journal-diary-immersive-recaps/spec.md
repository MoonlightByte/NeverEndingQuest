# journal-diary-immersive-recaps Specification

## Purpose
TBD - created by archiving change journal-diary-immersive-recap-refactor. Update Purpose after archive.
## Requirements
### Requirement: Diary entries expose immersive checkpoint metadata
The system SHALL persist and return explicit checkpoint metadata for each diary entry, including gameworld date, gameworld time, and primary location context captured at checkpoint creation time. When known, the system SHALL also persist module context and location identifier separately from the prose summary.

#### Scenario: Draft entry includes world-line stamp
- **WHEN** the Start Game diary hook creates or refreshes a draft checkpoint
- **THEN** the returned draft payload includes gameworld date/time metadata and a primary location label suitable for diary display

#### Scenario: Confirmed entry preserves historical location
- **WHEN** a Save or explicit Exit confirms a diary checkpoint and the party later travels elsewhere
- **THEN** the confirmed diary entry continues to expose the original checkpoint location metadata rather than the later current location

### Requirement: Diary summaries read as concise in-world recaps
The system SHALL generate diary summaries as short in-world recap text optimized for player recall. Each summary SHALL focus on where the party was, what materially happened there, and why that beat matters to the ongoing adventure, without turning into a full transcript or long-form chapter.

#### Scenario: Diary tab shows quick-reference prose
- **WHEN** the Journal modal requests diary data for display
- **THEN** each entry summary is concise enough for quick scanning and describes the checkpoint as an in-world recap rather than a raw source dump

#### Scenario: Diary summary supports current-worldline recall
- **WHEN** a player opens the Diary tab after a break in play
- **THEN** the summary helps the player recover the party's recent path and current narrative situation without needing to read full chat logs

### Requirement: Diary presentation remains compatible with existing Journal UI
The system SHALL surface the new checkpoint metadata through the existing diary route and Journal modal without breaking Quests behavior or requiring a full Journal layout rewrite.

#### Scenario: Quests tab remains unchanged
- **WHEN** diary metadata support is added
- **THEN** the Quests tab continues to render through its existing path without diary-specific regressions

#### Scenario: Diary route remains safe when metadata is incomplete
- **WHEN** location or module metadata cannot be resolved for a checkpoint
- **THEN** the diary route still returns a safe entry payload with fallback labels instead of failing the Journal request


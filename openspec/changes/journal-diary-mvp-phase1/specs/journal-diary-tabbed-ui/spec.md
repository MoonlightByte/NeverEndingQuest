## ADDED Requirements

### Requirement: Journal modal SHALL expose Quests and Diary tabs
The Journal UI SHALL provide tabbed navigation with Quests and Diary views while preserving existing Quests functionality.

#### Scenario: Quests tab behavior preserved
- **WHEN** a user opens Journal and selects Quests
- **THEN** quest content renders using existing behavior with no regression in current quest data display

#### Scenario: Diary tab visible
- **WHEN** a user opens Journal
- **THEN** a Diary tab is available and can be selected without page reload

### Requirement: Diary tab MUST present draft and confirmed states distinctly
The Diary tab MUST render an unsaved draft section (when present) separately from confirmed timeline entries.

#### Scenario: Draft exists
- **WHEN** a draft diary entry is available
- **THEN** Diary displays a "Current Session (Unsaved Draft)" card before confirmed timeline entries

#### Scenario: No draft exists
- **WHEN** no draft diary entry is available
- **THEN** Diary displays only confirmed timeline entries and no draft card placeholder requiring dismissal

### Requirement: Diary timeline SHALL use game-world descending order
The Diary tab SHALL display confirmed entries sorted from newest to oldest by game-world sort key.

#### Scenario: Confirmed entries listed
- **WHEN** multiple confirmed entries are returned by the API
- **THEN** the top visible confirmed entry is the one with highest game-world sort key

### Requirement: Diary tab SHALL request data from dedicated journal endpoint
Diary UI data loading SHALL use a dedicated journal diary API and not repurpose quest-only payloads.

#### Scenario: Journal open triggers diary fetch
- **WHEN** Journal is opened or Diary tab is activated
- **THEN** client requests `/api/journal/diary` and renders returned draft/confirmed structures

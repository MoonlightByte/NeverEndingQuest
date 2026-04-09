# journal-diary-tabbed-ui Specification

## Purpose
TBD - created by archiving change journal-diary-storyteller-mvp. Update Purpose after archive.
## Requirements
### Requirement: Journal SHALL expose Quests and Diary views without regressing quest behavior
The Journal modal SHALL preserve the current Quests experience and SHALL add a Diary tab as an additive view rather than replacing quest rendering.

#### Scenario: Opening Journal preserves quest view functionality
- **WHEN** the user opens the Journal modal
- **THEN** the existing quest data request and quest rendering behavior SHALL remain functional

#### Scenario: User can switch to Diary view
- **WHEN** the user selects the Diary tab in the Journal modal
- **THEN** the modal SHALL render diary content without removing or corrupting the Quests tab state

### Requirement: Diary UI SHALL distinguish draft from confirmed entries
The Diary view SHALL present the current unsaved draft separately from the confirmed historical timeline.

#### Scenario: Draft card is shown when draft exists
- **WHEN** the diary API returns an active draft entry
- **THEN** the Diary UI SHALL render that draft first with explicit unsaved labeling distinct from confirmed entries

#### Scenario: Confirmed timeline is shown below draft
- **WHEN** the diary API returns confirmed entries
- **THEN** the Diary UI SHALL render them as the historical timeline beneath any active draft card

#### Scenario: Diary view remains valid when draft is absent
- **WHEN** no active draft entry exists
- **THEN** the Diary UI SHALL omit the draft card and SHALL still render confirmed entries correctly

### Requirement: Diary UI SHALL expose story download action
The Diary view SHALL provide a user action to download the confirmed-only "story so far" artifact.

#### Scenario: Download action is available from Diary tab
- **WHEN** the Diary tab is rendered
- **THEN** the UI SHALL expose a story download control linked to the story/PDF route

#### Scenario: Download action is resilient to request failure
- **WHEN** the story download request fails
- **THEN** the UI SHALL re-enable the control and SHALL surface a safe error outcome without breaking the Journal modal


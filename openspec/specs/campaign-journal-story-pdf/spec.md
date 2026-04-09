# campaign-journal-story-pdf Specification

## Purpose
TBD - created by archiving change journal-diary-storyteller-mvp. Update Purpose after archive.
## Requirements
### Requirement: Story compilation SHALL use confirmed diary entries only
The system SHALL build the downloadable "story so far" artifact from confirmed diary entries only and SHALL exclude draft diary content by design.

#### Scenario: Draft content is excluded from story source query
- **WHEN** the story compiler assembles source material for the downloadable story artifact
- **THEN** it SHALL query confirmed diary entries only and SHALL NOT include draft diary rows in the compilation input

#### Scenario: Story order follows world-time chronology
- **WHEN** multiple confirmed diary entries exist
- **THEN** the story compiler SHALL assemble them in deterministic world-time order for the output narrative

### Requirement: Story artifact generation SHALL support cache reuse
The system SHALL cache the generated story artifact using a fingerprint derived from confirmed diary content so unchanged confirmed history does not require redundant regeneration.

#### Scenario: Cached story is reused when confirmed fingerprint matches
- **WHEN** the confirmed diary fingerprint matches an existing cached story artifact
- **THEN** the system SHALL reuse that cached artifact instead of regenerating it

#### Scenario: Story is regenerated when confirmed fingerprint changes
- **WHEN** confirmed diary content changes and produces a new fingerprint
- **THEN** the system SHALL generate a new story artifact and SHALL update cache metadata accordingly

### Requirement: Story download SHALL fail safely
The story route SHALL provide a safe error response when generation or file rendering fails and SHALL not mutate confirmed diary state on failure.

#### Scenario: Story generation failure returns safe error response
- **WHEN** story text or PDF rendering fails during a download request
- **THEN** the route SHALL return a structured error response and SHALL leave confirmed diary data unchanged

#### Scenario: No confirmed entries yields non-corrupt response
- **WHEN** the user requests a story download and no confirmed diary entries exist
- **THEN** the system SHALL return a safe non-corrupt response rather than generating a malformed story artifact


## ADDED Requirements

### Requirement: Single Canonical Render Per Turn
The system SHALL present at most one canonical narration render for a completed turn, even when draft and block output paths are both available.

#### Scenario: Commit suppresses duplicate block render
- **WHEN** a stream attempt for a turn is committed successfully
- **THEN** subsequent block-style narration output for that same accepted turn is suppressed in player chat

#### Scenario: Superseded attempts remain non-canonical
- **WHEN** a stream attempt is superseded
- **THEN** its rendered draft content is never treated as canonical output for that turn

#### Scenario: Canonical history integrity
- **WHEN** retries occur and one attempt is eventually accepted
- **THEN** persisted canonical history contains only the accepted narration content

## ADDED Requirements

### Requirement: TTS Uses Canonical Narration Blocks
The system SHALL perform automatic narration TTS only on canonical block narration output in rollback mode.

#### Scenario: Intro narration autoplay
- **WHEN** intro narration message is emitted as canonical block output
- **THEN** TTS reads that block output and does not attempt sentence-sync stream playback

#### Scenario: Runtime narration autoplay
- **WHEN** canonical narration output arrives in chat
- **THEN** TTS autoplay behavior follows existing block-message logic

#### Scenario: Manual TTS continuity
- **WHEN** the user clicks a narration TTS button
- **THEN** manual TTS behavior remains available and unchanged

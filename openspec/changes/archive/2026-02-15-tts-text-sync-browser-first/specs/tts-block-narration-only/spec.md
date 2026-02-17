## MODIFIED Requirements

### Requirement: TTS Uses Canonical Narration Blocks
The system SHALL perform automatic narration TTS only on canonical block narration output in rollback mode, and any progressive on-screen reveal SHALL be derived from that canonical block content without enabling server-side draft stream rendering.

#### Scenario: Intro narration autoplay
- **WHEN** intro narration message is emitted as canonical block output
- **THEN** TTS reads that block output and does not attempt sentence-sync stream playback

#### Scenario: Runtime narration autoplay
- **WHEN** canonical narration output arrives in chat
- **THEN** TTS autoplay behavior follows existing block-message logic

#### Scenario: Manual TTS continuity
- **WHEN** the user clicks a narration TTS button
- **THEN** manual TTS behavior remains available and unchanged

#### Scenario: Synced reveal preserves canonical source
- **WHEN** synced text reveal is enabled for Browser TTS
- **THEN** the UI reveal animation uses the already-emitted canonical block text as source and does not require server stream delta events

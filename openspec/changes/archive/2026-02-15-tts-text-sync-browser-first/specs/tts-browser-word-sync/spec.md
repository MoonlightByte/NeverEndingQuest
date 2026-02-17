## ADDED Requirements

### Requirement: Browser TTS Word-Boundary Reveal
When Browser TTS sync mode is enabled, the system SHALL reveal narration text progressively according to browser word-boundary callbacks from the active utterance.

#### Scenario: Autoplay narration reveal follows speech
- **WHEN** a narration message autoplays with Browser TTS and sync mode enabled
- **THEN** visible text reveal progression is updated from browser boundary callback positions and tracks spoken words in order

#### Scenario: Manual replay reveal follows speech
- **WHEN** the user manually triggers Browser TTS on a narration message with sync mode enabled
- **THEN** reveal progression is synchronized to the same utterance boundary events for that playback session

### Requirement: Reveal State Handles Interruption Safely
The system MUST keep reveal state coherent when playback is interrupted, cancelled, or errors occur.

#### Scenario: User stops playback mid narration
- **WHEN** Browser TTS is stopped before utterance completion
- **THEN** the UI clears speaking indicators, preserves already-revealed text, and does not corrupt message content

#### Scenario: Playback error fallback
- **WHEN** Browser TTS fires an error event during synced reveal
- **THEN** the UI exits speaking state and leaves a readable message without frozen cursor or duplicate text fragments

### Requirement: Sync Degrades to Existing Block Rendering
If precise boundary synchronization is unavailable, the system SHALL fall back to the existing block narration render path while preserving TTS playback availability.

#### Scenario: Boundary callback unavailable
- **WHEN** browser runtime does not provide usable word-boundary events
- **THEN** narration remains readable as standard block text and TTS playback behavior remains functional

## ADDED Requirements

### Requirement: Sync Strategy Contract
The frontend TTS pipeline SHALL resolve a sync strategy per playback request and use that strategy consistently for queue, playback, and reveal updates.

#### Scenario: Browser engine selects precise strategy
- **WHEN** the selected TTS engine is Browser TTS and sync mode is enabled
- **THEN** the request resolves to a boundary-driven sync strategy and reveal updates consume boundary positions

#### Scenario: Unsupported engine selects neutral strategy
- **WHEN** the selected TTS engine does not provide precise boundary timing in this change scope
- **THEN** the request resolves to a neutral strategy that preserves existing block render behavior

### Requirement: Queue Metadata Carries Sync Intent
The queue manager MUST preserve sync metadata with each queued narration request so playback and render handlers cannot confuse strategy across messages.

#### Scenario: Multiple narration messages queued
- **WHEN** consecutive narration messages are queued with mixed sync capability
- **THEN** each message is processed with its own resolved sync strategy and no cross-message state leakage occurs

### Requirement: Future Estimated-Timing Path Is Scaffolded, Not Active
The system SHALL expose a bounded extension point for non-browser timing-estimation strategies without enabling estimated sync behavior by default in this change.

#### Scenario: OpenAI TTS in current release scope
- **WHEN** OpenAI TTS is selected while this change is active
- **THEN** the system uses current non-sync block rendering behavior and does not claim precise per-word synchronization

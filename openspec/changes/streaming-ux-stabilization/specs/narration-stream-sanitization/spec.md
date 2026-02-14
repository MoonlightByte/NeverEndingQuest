## ADDED Requirements

### Requirement: Narration-Safe Draft Streaming
The system SHALL ensure streamed draft text displayed in player chat is narration-safe and does not expose raw JSON/control-plane tokens.

#### Scenario: Raw token leakage blocked
- **WHEN** the model emits JSON wrapper tokens during a streamed attempt
- **THEN** player-facing draft UI does not render raw braces, escaped control sequences, or non-narration scaffolding

#### Scenario: Narration-only deltas
- **WHEN** draft stream deltas are emitted to the frontend
- **THEN** each delta contributes to readable narration content intended for player display

#### Scenario: Fallback on non-sanitizable draft
- **WHEN** narration-safe draft extraction is unavailable for an attempt
- **THEN** the system falls back to non-stream block rendering for that attempt without exposing raw stream tokens

# tt-narrator-system-prompt-singularity Specification

## Purpose

Ensure outbound narrator payload assembly emits exactly one canonical main system prompt, with stable system-message ordering.
## Requirements
### Requirement: Outbound Narrator Payload SHALL Contain One Canonical Main Prompt

Narrator API payload assembly SHALL include exactly one canonical main narrator system prompt.

#### Scenario: Legacy + canonical prompt coexist in persisted history
- **GIVEN** conversation history contains legacy narrator prompt text and canonical compressed prompt text
- **WHEN** outbound message payload is assembled
- **THEN** runtime SHALL emit exactly one canonical main narrator prompt
- **AND** legacy duplicate prompt entries SHALL be excluded

#### Scenario: Compressor replacement attempts second canonical prompt
- **GIVEN** compressor replacement logic rewrites legacy prompt content
- **WHEN** final payload dedupe pass runs
- **THEN** only one canonical main prompt SHALL remain in outbound payload

### Requirement: Main Prompt Ordering SHALL Remain Stable

The single canonical main prompt SHALL remain first among system messages.

#### Scenario: Reordered system contexts
- **GIVEN** multiple system context messages are present
- **WHEN** ordering logic runs
- **THEN** canonical main prompt SHALL be first system message
- **AND** other system contexts SHALL preserve relative order after it

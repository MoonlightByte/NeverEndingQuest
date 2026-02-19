## ADDED Requirements

### Requirement: Usage tracker SHALL expose provider-agnostic interfaces
The system SHALL provide a provider-neutral usage tracking interface that does not require provider-branded naming in new integrations.

#### Scenario: Generic tracker used for usage record
- **WHEN** a chat completion response contains usage metadata (`prompt_tokens`, `completion_tokens`, `total_tokens`) and model identifier
- **THEN** usage SHALL be recorded without assuming a specific provider brand

#### Scenario: Legacy import compatibility preserved
- **WHEN** existing code imports `utils.openai_usage_tracker` helper functions
- **THEN** those calls SHALL continue to work with unchanged signatures and safe-return behavior

### Requirement: Tracker SHALL compute session and rolling-week token totals
The tracker SHALL maintain token counters for current process session and rolling-week windows using timestamped usage events.

#### Scenario: Session counters
- **WHEN** usage events are recorded during active runtime
- **THEN** `session_tokens` SHALL equal the sum of all tracked `total_tokens` since process start

#### Scenario: Rolling-week counters
- **WHEN** usage events exist across multiple timestamps
- **THEN** `week_tokens` SHALL include only events within configured rolling window and exclude older events

### Requirement: Tracker SHALL be thread-safe and failure tolerant
Tracker updates and reads SHALL be safe under concurrent usage and SHALL degrade gracefully on malformed historical telemetry lines.

#### Scenario: Concurrent updates
- **WHEN** multiple threads record usage simultaneously
- **THEN** aggregate counters SHALL remain internally consistent and non-negative

#### Scenario: Malformed telemetry bootstrap lines
- **WHEN** rolling-week bootstrap reads malformed telemetry entries
- **THEN** malformed lines SHALL be skipped without aborting tracker initialization

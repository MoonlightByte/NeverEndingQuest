# provider-agnostic-usage-tracking Specification

## Purpose
TBD - created by archiving change debug-usage-session-week-nzd-rollup. Update Purpose after archive.
## Requirements
### Requirement: Usage tracker SHALL expose provider-agnostic interfaces
The system SHALL provide provider-neutral tracking interfaces that support token-bearing events and non-token cost-only events.

#### Scenario: Generic cost-only tracker call
- **WHEN** image generation code records a successful generation using a cost-only tracker helper
- **THEN** usage aggregation SHALL update cost rollups without requiring provider-branded APIs

### Requirement: Tracker SHALL compute session and rolling-week token totals
The tracker SHALL maintain token counters for current process session and rolling-week windows using timestamped usage events.

#### Scenario: Cost-only image event does not affect token counters
- **WHEN** a successful image generation event is tracked without token usage metadata
- **THEN** `session_tokens` and `week_tokens` SHALL remain unchanged by that event
- **AND** session/week cost totals SHALL still update for that event

### Requirement: Tracker SHALL be thread-safe and failure tolerant
Tracker updates and reads SHALL be safe under concurrent usage and SHALL degrade gracefully on malformed historical telemetry lines.

#### Scenario: Concurrent updates
- **WHEN** multiple threads record usage simultaneously
- **THEN** aggregate counters SHALL remain internally consistent and non-negative

#### Scenario: Malformed telemetry bootstrap lines
- **WHEN** rolling-week bootstrap reads malformed telemetry entries
- **THEN** malformed lines SHALL be skipped without aborting tracker initialization


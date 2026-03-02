## ADDED Requirements

### Requirement: Startup shall remove stale recap constraints from runtime histories
The startup sequence SHALL remove stale recap messages containing `SESSION RESUME RECAP ONLY` from both `conversation_history.json` and `chat_history.json` before startup recap injection occurs.

#### Scenario: Startup removes stale recap messages from both files
- **WHEN** either history file contains one or more stale recap messages
- **THEN** all stale recap messages are removed from that file before recap injection
- **AND** the cleaned history is persisted to disk
- **AND** logs include per-file removal counts

#### Scenario: Startup performs no-op cleanup when no stale recaps exist
- **WHEN** both files contain no stale recap messages
- **THEN** startup leaves message arrays unchanged
- **AND** startup continues normal recap injection flow

### Requirement: Startup cleanup shall be idempotent and fail-open
Startup cleanup SHALL be safe across repeated restarts and SHALL not block server startup when cleanup encounters file access or parse errors.

#### Scenario: Repeated startup remains stable
- **WHEN** startup cleanup runs multiple times with no new stale recap messages
- **THEN** each run removes zero additional messages
- **AND** no duplicate side effects are introduced

#### Scenario: Missing or malformed history file
- **WHEN** a target history file is missing or malformed
- **THEN** startup logs a degraded cleanup status for that file
- **AND** startup continues without terminating the server process
- **AND** gameplay validation fail-closed behavior remains unchanged

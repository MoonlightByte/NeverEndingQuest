# tt-web-creation-session-recovery Specification

## Purpose
TBD - created by archiving change web-dm-creation-session-hardening. Update Purpose after archive.
## Requirements
### Requirement: Web Create-with-DM activation SHALL fail closed
The `/api/party/create_player` route SHALL only report success after creation-session activation state is fully established. If activation cannot be completed safely, the route SHALL fail closed and SHALL not leave a stale creation marker behind.

#### Scenario: Marker write fails during activation
- **WHEN** `/api/party/create_player` cannot persist `modules/conversation_history/creation_mode_active.json`
- **THEN** the route returns an error response
- **AND** no success payload is emitted
- **AND** no stale active creation marker remains on disk

#### Scenario: Post-marker activation step fails
- **WHEN** `/api/party/create_player` creates or updates backup state and marker state but a later activation step fails before route completion
- **THEN** the route invokes the shared character-creation abort helper
- **AND** prior conversation state is restored when backup is available
- **AND** stale retry artifacts and marker state are cleaned before the error response is returned

### Requirement: Web Create-with-DM finalization SHALL distinguish retryable and terminal failures
The `/api/party/finalize_creation` route SHALL preserve active creation mode for repairable invalid-final results and SHALL abort the creation session for terminal failures.

#### Scenario: Repairable invalid final payload keeps creation active
- **WHEN** the shared finalizer returns `not_candidate` or `needs_retry`
- **THEN** `/api/party/finalize_creation` returns a client-error response with corrective guidance
- **AND** the active creation marker remains intact
- **AND** the route does not invoke terminal session cleanup

#### Scenario: Shared finalizer returns terminal error
- **WHEN** the shared finalizer returns `error` or an unexpected terminal status
- **THEN** `/api/party/finalize_creation` invokes the shared character-creation abort helper
- **AND** the route returns a server-error response
- **AND** no stale active creation marker remains after the response

#### Scenario: Character persistence fails after successful finalization
- **WHEN** the shared finalizer returns `success` but `persist_dm_created_character(...)` fails
- **THEN** `/api/party/finalize_creation` invokes the shared character-creation abort helper
- **AND** the route returns a server-error response
- **AND** prior conversation state is restored when backup is available

### Requirement: Web route cleanup SHALL preserve startup and single-player compatibility
Web route hardening SHALL be additive and SHALL not regress startup recovery or single-player operation.

#### Scenario: Startup recovery remains compatible after web route cleanup
- **WHEN** a previously poisoned creation session exists at process startup
- **THEN** the existing startup recovery path continues to recover it without requiring additional route-only state

#### Scenario: Single-player gameplay without Create-with-DM remains unchanged
- **WHEN** the user does not enter the web Create-with-DM flow
- **THEN** gameplay, startup, and Roll Your Own behavior remain unchanged


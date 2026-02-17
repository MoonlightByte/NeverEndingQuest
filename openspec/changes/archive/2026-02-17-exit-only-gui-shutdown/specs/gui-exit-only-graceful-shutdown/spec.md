## ADDED Requirements

### Requirement: GUI Exit SHALL initiate intentional server shutdown
The system SHALL treat SocketIO `user_exit` as an intentional shutdown request and begin server shutdown from the existing web process.

#### Scenario: Exit request with active socket connection
- **WHEN** the user confirms Exit in the GUI and emits `user_exit`
- **THEN** the server emits `exit_acknowledged`
- **AND** begins shutdown flow from the server process

#### Scenario: Exit handler encounters shutdown exception
- **WHEN** graceful shutdown path raises an exception
- **THEN** the server still exits intentionally using dedicated shutdown return code
- **AND** does not remain running indefinitely

### Requirement: Launcher MUST distinguish intentional GUI shutdown from restart events
`run_web.py` MUST treat return code `91` as intentional user shutdown and MUST NOT auto-restart in this path.

#### Scenario: Intentional GUI shutdown return code
- **WHEN** `web/web_interface.py` exits with return code `91`
- **THEN** `run_web.py` prints shutdown message and exits launcher loop
- **AND** no automatic restart occurs

#### Scenario: Existing restart return code remains active
- **WHEN** web process exits with return code `0`
- **THEN** launcher restart behavior remains unchanged

### Requirement: Exit-only Phase 1 MUST preserve existing reset/restore restart semantics
The implementation MUST keep reset/restore flows operational with their current restart behavior.

#### Scenario: Reset or restore completion path
- **WHEN** reset/restore triggers normal restart exit path
- **THEN** launcher still performs automatic restart
- **AND** no GUI Exit-specific logic interferes with that path

### Requirement: GUI SHALL show deterministic shutdown waiting state
The client SHALL provide immediate visual feedback after Exit confirmation and prevent new user input while shutdown is in progress.

#### Scenario: Exit confirmation accepted
- **WHEN** user confirms Exit in the browser
- **THEN** shutdown message/overlay is displayed
- **AND** input controls are disabled until process disconnect

## ADDED Requirements

### Requirement: Module integration SHALL not execute in ordinary live-turn processing
Automatic module detection and integration SHALL be excluded from ordinary gameplay turn processing and context refresh paths.

#### Scenario: Standard player turn executes
- **WHEN** the runtime processes a normal player turn during active gameplay
- **THEN** module detection and integration SHALL NOT run in that hot path
- **AND** live narrator context assembly SHALL remain isolated from module onboarding side effects

### Requirement: Failed module integration SHALL be quarantined from scene context
When module safety validation fails, the failure SHALL be quarantined from active narrator and reconciliation context.

#### Scenario: A discovered module fails safety validation
- **WHEN** automatic or explicit module integration detects a module that fails safety validation
- **THEN** the failure SHALL be logged in a dedicated diagnostic path
- **AND** repeated ordinary turns SHALL NOT retry integration automatically without a state change or explicit operator action
- **AND** failed integration output SHALL NOT be injected into live narrator payload assembly

#### Scenario: No new modules are pending
- **WHEN** there are no operator-approved module integration actions pending
- **THEN** ordinary live turns SHALL proceed without module integration checks or logs

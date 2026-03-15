## Purpose

Define start-game strict preflight gating for unresolved monster references with one deterministic remediation attempt.

## Requirements

### Requirement: Start-game preflight SHALL run strict monster reference integrity gating

Before launching gameplay, the start-game flow SHALL validate module monster reference integrity and SHALL enforce strict publish-gate behavior.

#### Scenario: Reference integrity already passes

- **WHEN** start-game preflight runs and `reference_integrity.failed == 0`
- **THEN** gameplay startup SHALL continue unchanged
- **AND** remediation SHALL NOT execute

#### Scenario: First-run bootstrap bypasses strict module validation

- **WHEN** start-game preflight detects startup bootstrap state (for example missing tracker, no active module, empty party, or missing primary character file)
- **THEN** gameplay startup SHALL continue into startup wizard initialization
- **AND** strict monster reference validation SHALL NOT block first-run setup

#### Scenario: One remediation attempt before terminal decision

- **WHEN** preflight detects unresolved monster references
- **THEN** startup SHALL execute exactly one deterministic remediation attempt
- **AND** startup SHALL run a second validation pass immediately after remediation

#### Scenario: Post-remediation unresolved references block startup

- **WHEN** post-remediation validation still reports unresolved monster references
- **THEN** start-game SHALL fail closed
- **AND** error output SHALL include actionable operator guidance with module context

#### Scenario: Post-remediation pass allows startup

- **WHEN** post-remediation validation reports zero unresolved monster references
- **THEN** start-game SHALL proceed
- **AND** no degraded-mode bypass SHALL be used

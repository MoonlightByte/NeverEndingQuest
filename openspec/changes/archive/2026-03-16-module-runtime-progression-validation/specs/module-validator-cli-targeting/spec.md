## MODIFIED Requirements

### Requirement: Module Validator CLI Targeting
The schema validator CLI SHALL support explicit target selection for module validation runs, and SHALL execute the same full validation suite for both human-readable and JSON reporting paths.

#### Scenario: Validate by module slug
- **WHEN** an operator runs `validate_module_files.py --module <slug>`
- **THEN** the validator SHALL resolve `modules/<slug>` and run the full validation suite on that module only
- **AND** it SHALL return a deterministic success/failure exit code.

#### Scenario: Validate by module path
- **WHEN** an operator runs `validate_module_files.py --module-path <path>`
- **THEN** the validator SHALL validate that exact module path
- **AND** it SHALL fail with a clear error if the path does not exist or is not module-like.

#### Scenario: Help works without validator dependency
- **WHEN** `jsonschema` is unavailable and the operator runs `validate_module_files.py --help`
- **THEN** help output SHALL still render successfully
- **AND** no import traceback SHALL be shown.

#### Scenario: Dependency unavailable during validation
- **WHEN** `jsonschema` is unavailable and a validation run is requested
- **THEN** the tool SHALL fail with a clear dependency message and install guidance
- **AND** it SHALL return a non-zero exit code.

#### Scenario: Human and JSON modes execute the same validation suite
- **WHEN** an operator runs validation with standard human-readable output
- **AND** another operator runs validation against the same module with `--json`
- **THEN** both executions SHALL run the same validation checks
- **AND** neither path SHALL silently skip connectivity or progression validation steps

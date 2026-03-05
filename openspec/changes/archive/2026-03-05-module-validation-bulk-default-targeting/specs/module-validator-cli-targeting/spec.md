## ADDED Requirements

### Requirement: Module Validator CLI Targeting
The schema validator CLI SHALL support explicit target selection for module validation runs.

#### Scenario: Validate by module slug
- WHEN an operator runs `validate_module_files.py --module <slug>`
- THEN the validator SHALL resolve `modules/<slug>` and run the full validation suite on that module only
- AND it SHALL return a deterministic success/failure exit code.

#### Scenario: Validate by module path
- WHEN an operator runs `validate_module_files.py --module-path <path>`
- THEN the validator SHALL validate that exact module path
- AND it SHALL fail with a clear error if the path does not exist or is not module-like.

#### Scenario: Help works without validator dependency
- WHEN `jsonschema` is unavailable and the operator runs `validate_module_files.py --help`
- THEN help output SHALL still render successfully
- AND no import traceback SHALL be shown.

#### Scenario: Dependency unavailable during validation
- WHEN `jsonschema` is unavailable and a validation run is requested
- THEN the tool SHALL fail with a clear dependency message and install guidance
- AND it SHALL return a non-zero exit code.

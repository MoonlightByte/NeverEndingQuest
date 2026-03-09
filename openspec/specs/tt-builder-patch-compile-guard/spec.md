# tt-builder-patch-compile-guard Specification

## Purpose
TBD - created by archiving change tt-combat-manager-hardening-only. Update Purpose after archive.
## Requirements
### Requirement: Builder Syntax Guard Script SHALL Validate Touched Python Files
The repository SHALL provide a script that compiles specified Python files and fails fast on syntax errors.

#### Scenario: All files compile
- **WHEN** script runs with one or more valid Python file paths and all compile successfully
- **THEN** script SHALL print per-file pass results
- **AND** script SHALL exit with status code 0

#### Scenario: One or more files fail compile
- **WHEN** script runs and at least one target file has syntax/indentation errors
- **THEN** script SHALL print per-file failure diagnostics
- **AND** script SHALL exit non-zero

### Requirement: Syntax Guard SHALL Be Safe for Builder Workflows
The compile guard utility SHALL remain read-only and non-destructive.

#### Scenario: Script execution
- **WHEN** script is executed during builder patch loop
- **THEN** script SHALL not modify source files
- **AND** script SHALL only perform compile checks and reporting

### Requirement: TT Hardening Workflow SHALL Use Compile Guard in Verification
TT-only refactor steps SHALL include compile guard verification.

#### Scenario: Refactor task verification
- **WHEN** TT refactor task is marked complete
- **THEN** verification SHALL include compile checks for all touched Python files
- **AND** task completion SHALL be blocked if compile guard reports failure


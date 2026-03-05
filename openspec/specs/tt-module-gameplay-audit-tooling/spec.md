## Purpose

Define a stable gameplay-audit contract for tabletop module monster validation, including blocking issue detection and baseline coverage comparison.

## Requirements

### Requirement: A gameplay audit command SHALL detect runtime blockers
The repository SHALL provide a script that audits monster reference resolution and reports blocking issues separately from warnings.

#### Scenario: Blocking resolution failures
- **WHEN** a referenced monster JSON is missing
- **THEN** the audit script reports it under `blocking_errors` and exits nonzero

#### Scenario: Coverage reporting
- **WHEN** audit script completes
- **THEN** output includes `coverage_stats` and a concrete `fix_list`

### Requirement: Baseline comparison SHALL be available
The audit script SHALL support optional baseline comparison against another module.

#### Scenario: Baseline mode run
- **WHEN** `--baseline <module>` is provided
- **THEN** the report includes comparative coverage indicators

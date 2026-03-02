## ADDED Requirements

### Requirement: Cleanup script shall mirror runtime stale recap logic
`scripts/cleanup_stale_recaps.py` SHALL call shared cleanup utilities used by startup runtime and SHALL not maintain duplicate stale recap matching logic.

#### Scenario: Runtime and script produce same removals
- **WHEN** both runtime cleanup and script cleanup are run against the same fixture histories
- **THEN** both paths remove the same set of stale recap messages
- **AND** both paths report consistent removal counts

### Requirement: Cleanup script shall support safe dry-run and explicit apply modes
The cleanup script SHALL provide deterministic `--dry-run` and `--apply` behavior suitable for developer diagnostics.

#### Scenario: Dry-run mode
- **WHEN** script runs with `--dry-run`
- **THEN** it reports what would be removed
- **AND** it does not modify any history file

#### Scenario: Apply mode
- **WHEN** script runs with `--apply`
- **THEN** it persists stale recap removals to target files
- **AND** it reports per-file before/after counts and removal totals

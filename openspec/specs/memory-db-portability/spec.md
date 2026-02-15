## ADDED Requirements

### Requirement: Memory DB export SHALL produce a portable package with manifest
The system SHALL support exporting memory DB state into a portable package that includes DB artifact and manifest metadata.

#### Scenario: Export package creation
- **WHEN** operator runs memory export command
- **THEN** a DB artifact copy is produced
- **AND** a manifest JSON is created with schema version, export timestamp, row-count summary, and integrity hash

### Requirement: Import SHALL validate compatibility before restore
The system MUST validate manifest and schema compatibility before importing memory data, including imports triggered by save-game restore workflows.

#### Scenario: Import with incompatible schema
- **WHEN** package manifest schema version is unsupported
- **THEN** import is rejected
- **AND** output indicates compatibility failure reason

#### Scenario: Save restore import validation failure
- **WHEN** save-game restore invokes memory import and validation fails
- **THEN** the restore operation reports failure
- **AND** restore is not marked successful

### Requirement: Import defaults SHALL be non-destructive
Import flow SHALL default to safe behavior and avoid overwriting existing DB without explicit operator override, except for managed save-restore paths that perform validated, explicit replacement semantics by design.

#### Scenario: Existing target DB without override
- **WHEN** target DB already exists and override flag is absent
- **THEN** import exits without modifying target DB

#### Scenario: Managed save restore replacement
- **WHEN** restore flow imports memory package through the managed save-restore path
- **THEN** import executes explicit replacement behavior only after package validation passes

### Requirement: Portability workflow SHALL support dry-run validation
Import tooling SHALL provide dry-run mode for validating package compatibility and projected actions without writing to target DB.

#### Scenario: Dry-run import
- **WHEN** operator runs import with `--dry-run`
- **THEN** compatibility and integrity checks are executed
- **AND** no files are written or replaced

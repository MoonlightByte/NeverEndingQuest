## ADDED Requirements

### Requirement: System SHALL restore campaign from validated archive zip
The restore workflow SHALL support selecting a zip archive and restoring campaign state via validated staging.

#### Scenario: Restore from valid zip archive
- **WHEN** operator selects a valid archive zip from `archive_exports/`
- **THEN** system validates archive metadata and structure
- **AND** stages extracted save folder to canonical module save path
- **AND** delegates to existing folder restore logic

### Requirement: Zip restore SHALL fail closed on invalid archive
Zip restore SHALL reject malformed or unsafe archives with explicit error output and no false success.

#### Scenario: Invalid zip is rejected
- **WHEN** archive is malformed, missing required metadata, or fails preflight checks
- **THEN** restore returns failure with explicit error message
- **AND** no restore success event is emitted

### Requirement: Zip extraction SHALL enforce traversal safety
Archive extraction SHALL block path traversal and absolute path entries.

#### Scenario: Traversal entry detected
- **WHEN** zip entry contains `..` segments or absolute paths
- **THEN** preflight validation fails and extraction is aborted

### Requirement: Existing folder restore SHALL remain compatible
Adding zip restore SHALL NOT change behavior of existing folder-based restore actions.

#### Scenario: Folder restore path unchanged
- **WHEN** operator restores using existing save folder selection
- **THEN** existing restore behavior and restart semantics remain unchanged

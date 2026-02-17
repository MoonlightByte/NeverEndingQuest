# campaign-archive-root-export Specification

## Purpose
TBD - created by archiving change archive-root-export-and-zip-import-restore. Update Purpose after archive.
## Requirements
### Requirement: Full save SHALL write archive zip to repo-root export folder
When Archive Edition save is executed (`save_mode=full`), the generated zip artifact SHALL be written to a repo-root archive export directory.

#### Scenario: Full save writes zip to root export folder
- **WHEN** operator runs save with `save_mode=full`
- **THEN** backend creates zip artifact under `archive_exports/`
- **AND** save success payload includes `zip_path`, `zip_name`, and `bytes`

### Requirement: Archive export naming SHALL be deterministic and operator-readable
Zip artifact names SHALL be deterministic and include module and save identity context.

#### Scenario: Deterministic archive filename generated
- **WHEN** full save zip is generated
- **THEN** filename format includes module, timestamp, and save folder identity
- **AND** resulting filename is ASCII-safe and filesystem-safe

### Requirement: Essential save SHALL remain unchanged
Changing full-save archive export location SHALL NOT alter essential save behavior.

#### Scenario: Essential save preserves legacy payload
- **WHEN** operator runs save with `save_mode=essential`
- **THEN** save succeeds with legacy content-only success payload
- **AND** no archive zip generation is attempted


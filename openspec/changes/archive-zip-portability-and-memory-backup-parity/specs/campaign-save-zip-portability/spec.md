## ADDED Requirements

### Requirement: Archive save SHALL auto-generate a portable zip artifact
The system SHALL automatically generate a single portable zip artifact whenever GUI save is executed in `Archive Edition` (`save_mode=full`), without requiring additional GUI controls.

#### Scenario: Full save triggers zip generation
- **WHEN** the operator runs save with `save_mode=full`
- **THEN** backend save flow emits a zip artifact and includes artifact status/path in save result

### Requirement: Archive zip SHALL include memory parity artifacts when present
The archive zip SHALL include `memory_db_package/` and manifest content when memory parity artifacts exist at save time.

#### Scenario: Memory package is preserved in archive zip
- **WHEN** a full save includes `memory_db_package/`
- **THEN** the generated zip contains package files unchanged

### Requirement: Archive zip SHALL cover campaign-recoverable state for played modules
The archive zip SHALL include campaign data required to recover timelines for all modules played in the campaign session history.

#### Scenario: Multi-module campaign data appears in archive zip
- **WHEN** the campaign has played across more than one module
- **THEN** generated archive zip includes required data artifacts for each played module under the defined inclusion policy

### Requirement: Archive save SHALL fail if mandatory zip artifact generation fails
When `save_mode=full`, save completion SHALL be rejected if required zip artifact generation fails.

#### Scenario: Zip generation failure fails archive save
- **WHEN** zip generation fails during `save_mode=full`
- **THEN** the save operation returns failure with explicit error message and no false-success outcome

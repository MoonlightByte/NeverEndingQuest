## ADDED Requirements

### Requirement: Failed ingest artifacts SHALL be cleaned from modules root

The ingest pipeline SHALL prevent failed or quarantined runs from leaving orphan module directories under `modules/`.

#### Scenario: Quarantined ingest archives generated module folder

- **WHEN** ingest result is `quarantined`
- **AND** a generated module folder exists for that run slug
- **THEN** pipeline SHALL move that folder to `modules/ingest/archive/failed_<timestamp>_<slug>/`
- **AND** no orphan folder for that slug SHALL remain under `modules/`

#### Scenario: Failed ingest archives generated module folder

- **WHEN** ingest result is `failed`
- **AND** a generated module folder exists for that run slug
- **THEN** cleanup stage SHALL archive the folder using the same deterministic pattern

#### Scenario: Cleanup safety guard preserves active module

- **WHEN** cleanup is evaluating a slug that is active/registered
- **THEN** cleanup SHALL skip destructive actions for that slug
- **AND** stage output SHALL report safety skip reason

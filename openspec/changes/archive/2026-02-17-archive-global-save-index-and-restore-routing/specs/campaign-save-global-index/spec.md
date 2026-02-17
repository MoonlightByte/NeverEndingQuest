## ADDED Requirements

### Requirement: Global save catalog SHALL discover saves across module directories
The system SHALL provide a save catalog mode that discovers save folders under `modules/*/saved_games/save_*` and returns a single normalized list.

#### Scenario: Global list includes saves from multiple modules
- **WHEN** save folders exist in more than one module under `modules/*/saved_games/`
- **THEN** the global save catalog response includes entries from each module with no manual module switching

### Requirement: Save catalog entries SHALL include source module and parity visibility fields
Each global save entry SHALL include `source_module`, `save_folder`, and `memory_package_present` fields in addition to existing save metadata.

#### Scenario: Entry exposes source module and memory package presence
- **WHEN** the system returns a global save catalog entry
- **THEN** that entry includes the module owning the save folder and whether `memory_db_package/` is present

### Requirement: Global save catalog SHALL be deterministically ordered
The global save catalog SHALL sort entries by `save_timestamp` descending across all modules.

#### Scenario: Newest save appears first across modules
- **WHEN** saves from multiple modules are returned with different timestamps
- **THEN** the first entry in the response is the save with the latest timestamp regardless of module

## ADDED Requirements

### Requirement: Bulk Validation Default Target Resolution
Bulk module validation SHALL use deterministic default module selection when explicit selectors are not provided.

#### Scenario: Default set includes registry and module-like folders
- WHEN an operator runs bulk validation without explicit module selectors
- THEN the resolver SHALL include registered modules from `world_registry.json` whose folders exist
- AND it SHALL include module-like directories under `modules/` that contain `areas/*.json`.

#### Scenario: Default set excludes system folders
- WHEN the default resolver scans the `modules/` directory
- THEN it SHALL exclude non-module/system folders and hidden folders
- AND it SHALL not attempt to validate archive, ingest, history, or other non-play data folders.

#### Scenario: Deterministic execution order
- WHEN the resolved module set is built
- THEN targets SHALL be de-duplicated and sorted deterministically before validation execution.

### Requirement: Bulk Validation Aggregate Outcome
Bulk validation SHALL report per-module outcomes and a deterministic final status.

#### Scenario: Aggregate pass
- WHEN all selected modules pass schema validation and no blocking gameplay audit errors are found
- THEN the command SHALL exit with code `0`.

#### Scenario: Aggregate fail
- WHEN any selected module has schema failures, blocking gameplay audit errors, or execution failures
- THEN the command SHALL exit non-zero
- AND it SHALL identify failing modules in summary output.

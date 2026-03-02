## ADDED Requirements

### Requirement: Successful strict ingest MUST register module in world registry
After strict validation passes, the ingest pipeline MUST register the module in `world_registry.json` using the canonical integration path.

#### Scenario: Validation passes and registration succeeds
- **WHEN** strict ingest validation passes for emitted artifacts
- **THEN** the system registers the module in `world_registry.modules`
- **AND** ingest result status is `success`

#### Scenario: Validation passes but registration fails
- **WHEN** strict ingest validation passes but registry integration throws or reports failure
- **THEN** ingest result status is `quarantined`
- **AND** `quarantine_reason` is `registry_integration_failed`

### Requirement: Ingest success SHALL require registry presence confirmation
Ingest SHALL NOT return `success` unless module presence in `world_registry.modules` is confirmed.

#### Scenario: Registration function returns without exception but module missing
- **WHEN** registration call completes but module key is absent from world registry
- **THEN** ingest result is `quarantined`
- **AND** registration error details are included in result payload

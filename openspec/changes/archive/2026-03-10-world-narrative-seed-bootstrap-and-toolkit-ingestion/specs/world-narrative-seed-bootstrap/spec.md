## ADDED Requirements

### Requirement: Runtime DB bootstrap SHALL copy seed DB only when runtime DB is missing
The system SHALL support first-run bootstrap from `data/world_narrative_seed.db` to `data/memory.db` and SHALL NOT overwrite an existing runtime DB.

#### Scenario: Runtime missing and seed exists
- **WHEN** runtime DB path does not exist and seed DB path exists
- **THEN** the system copies seed DB to runtime DB and logs bootstrap success

#### Scenario: Runtime already exists
- **WHEN** runtime DB path already exists
- **THEN** the system skips bootstrap and does not overwrite runtime data

#### Scenario: Seed missing
- **WHEN** seed DB path is missing
- **THEN** the system skips bootstrap and proceeds with standard runtime initialization

### Requirement: World model schema migration MUST be additive and idempotent
The system MUST add and preserve additive tables for world-narrative convergence and interpreted model versioning without destructive changes.

#### Scenario: Migration applied on fresh DB
- **WHEN** migrations run against a DB without world-model tables
- **THEN** tables `atom_relations`, `atom_statistics`, `campaign_world_model`, and `campaign_world_delta` are created

#### Scenario: Migration rerun on existing DB
- **WHEN** migrations run a second time
- **THEN** migration succeeds without duplicate-table or data-loss errors

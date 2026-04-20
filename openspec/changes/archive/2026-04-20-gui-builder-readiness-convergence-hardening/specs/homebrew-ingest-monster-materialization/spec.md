## MODIFIED Requirements

### Requirement: Successful ingest SHALL materialize module monster stat files

After strict ingest success, the pipeline SHALL materialize monster stat files into `modules/<slug>/monsters/` from bestiary-backed seed data so tabletop fail-closed combat can start encounters.

#### Scenario: Seeded monster maps to bestiary entry

- **WHEN** `monsters_seed.json` contains a monster that resolves in `data/bestiary/monster_compendium.json`
- **THEN** pipeline SHALL create `modules/<slug>/monsters/<normalized_name>.json`
- **AND** created file SHALL include schema-compatible fields required by combat loader paths

#### Scenario: Materialized monster remains schema-complete after repair
- **WHEN** a materialized or generated module monster file already exists but is missing required monster-schema fields
- **AND** deterministic source data exists to backfill those fields safely
- **THEN** remediation SHALL repair the file to a schema-complete state
- **AND** readiness SHALL revalidate against the repaired file rather than treating file existence alone as success

#### Scenario: Schema-complete repair cannot be proven safely
- **WHEN** a materialized or generated module monster file is missing required fields
- **AND** deterministic source data is insufficient to backfill them safely
- **THEN** remediation SHALL classify the result as residual monster-schema debt
- **AND** readiness SHALL fail closed rather than writing guessed values

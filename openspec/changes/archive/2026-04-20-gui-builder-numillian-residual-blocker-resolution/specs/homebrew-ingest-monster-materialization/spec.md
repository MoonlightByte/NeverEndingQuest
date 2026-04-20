## MODIFIED Requirements

### Requirement: Successful ingest SHALL materialize module monster stat files

After strict ingest success, the pipeline SHALL materialize monster stat files into `modules/<slug>/monsters/` from bestiary-backed seed data so tabletop fail-closed combat can start encounters.

#### Scenario: Validator-derived missing monster path is actionable

- **WHEN** readiness remediation receives a validator error containing an expected monster path under `modules/<slug>/monsters/`
- **THEN** monster closure SHALL target that exact normalized slug/path rather than only authored hydration candidates
- **AND** the result SHALL report whether the file was created, reused, already existed, or remained unresolved

#### Scenario: Existing monster schema can be completed from authoritative source

- **WHEN** an existing module monster file is missing required schema fields such as `size`, `alignment`, or `armorClass`
- **AND** authoritative source data for that monster exists
- **THEN** schema completion SHALL backfill only those missing fields
- **AND** the repair result SHALL identify the changed file

#### Scenario: Existing monster schema cannot be completed safely

- **WHEN** an existing module monster file is missing required schema fields
- **AND** no authoritative source data exists for those fields
- **THEN** remediation SHALL fail closed for that file
- **AND** reporting SHALL classify the result as residual schema debt rather than synthetic success

## ADDED Requirements

### Requirement: Existing monster files SHALL support authoritative schema completion

Materialization-adjacent repair paths SHALL support schema completion for existing monster files when authoritative source data is available.

#### Scenario: Existing monster file is schema-incomplete but source-backed

- **WHEN** an existing `modules/<slug>/monsters/*.json` file is missing required schema fields
- **AND** authoritative source data exists for that monster
- **THEN** residual repair SHALL backfill the missing fields atomically
- **AND** subsequent validator runs SHALL no longer fail on those repaired fields

#### Scenario: Existing monster file is schema-incomplete without source support

- **WHEN** an existing monster file is missing required fields
- **AND** authoritative source data does not exist for safe backfill
- **THEN** residual repair SHALL fail closed for that file
- **AND** reporting SHALL classify it as unresolved schema-completion debt

### Requirement: Materialization SHALL accept validator-derived closure targets

Monster closure SHALL support target sets derived from validator reference-integrity failures, not only authored hydration candidates.

#### Scenario: Missing reference appears only in validator output

- **WHEN** validation reports an expected monster file path absent from authored hydration candidates
- **THEN** residual closure SHALL still attempt deterministic resolution for that target
- **AND** SHALL report whether the reference was materialized, reused, or remained unresolved

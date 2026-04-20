# homebrew-ingest-monster-materialization Specification

## Purpose
TBD - created by archiving change homebrew-ingest-working-adventure-hardening. Update Purpose after archive.
## Requirements
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

### Requirement: Monster closure SHALL reconcile validator-visible structured monsters with authority filtering

Deterministic monster closure SHALL not fail solely because the same normalized identity also appears in module NPC catalogs when the validator-visible authored usage is an explicit structured monster reference.

#### Scenario: Structured monster reference shares identity with NPC catalog entry

- **WHEN** a module authors a slug in `locations[].monsters[]`
- **AND** the same slug also appears in an NPC catalog surface
- **THEN** deterministic monster closure SHALL still treat the structured monster evidence as eligible for reconciliation
- **AND** SHALL NOT fail with `unauthorized_monster_reference` solely due to the NPC catalog overlap

### Requirement: Monster schema completion SHALL use bounded canonical recovery

Deterministic schema completion SHALL attempt safe authoritative canonical recovery when a monster slug does not exactly match the compendium identity.

#### Scenario: Singular/plural recovery resolves authoritative source

- **WHEN** a module monster file is missing required schema fields
- **AND** exact compendium lookup for its slug fails
- **AND** a bounded canonical variant such as singular/plural recovery resolves to one authoritative source entry
- **THEN** schema completion SHALL backfill from that authoritative source
- **AND** SHALL report the recovery mode used

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


# homebrew-ingest-monster-materialization Specification

## Purpose
TBD - created by archiving change homebrew-ingest-working-adventure-hardening. Update Purpose after archive.
## Requirements
### Requirement: Successful ingest SHALL materialize module monster stat files

Shared monster materialization SHALL execute through a stable Python helper contract for ingest and toolkit-finishing flows so tabletop fail-closed combat can start encounters without depending on fragile subprocess import context.

#### Scenario: Seeded monster maps to bestiary entry

- **WHEN** `monsters_seed.json` contains a monster that resolves in `data/bestiary/monster_compendium.json`
- **THEN** materialization SHALL create `modules/<slug>/monsters/<normalized_name>.json`
- **AND** created file SHALL include schema-compatible fields required by combat loader paths

#### Scenario: Seeded monster does not map to bestiary entry

- **WHEN** `monsters_seed.json` contains a monster with no bestiary match
- **THEN** materialization SHALL report unresolved mapping in structured output
- **AND** pipeline SHALL mark run as degraded unless strict materialization mode is enabled

#### Scenario: Existing monster file is preserved

- **WHEN** `modules/<slug>/monsters/<normalized_name>.json` already exists
- **THEN** materialization SHALL skip overwrite by default
- **AND** stage summary SHALL increment skipped-existing count

#### Scenario: Toolkit finisher uses shared in-process materialization

- **WHEN** the toolkit post-build finisher runs monster materialization for a built module
- **THEN** it MUST call the shared Python materialization helper directly
- **AND** MUST NOT rely on subprocess cwd or `PYTHONPATH` state to import repo modules

#### Scenario: Script wrapper remains a thin CLI adapter

- **WHEN** `scripts/homebrew_materialize_monsters.py` is executed from the command line
- **THEN** it MUST delegate to the same shared materialization helper used by ingest and toolkit flows
- **AND** MUST preserve structured output parity with in-process callers

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


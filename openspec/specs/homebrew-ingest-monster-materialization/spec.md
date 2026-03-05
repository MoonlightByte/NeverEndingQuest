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

#### Scenario: Seeded monster does not map to bestiary entry

- **WHEN** `monsters_seed.json` contains a monster with no bestiary match
- **THEN** materialization stage SHALL report unresolved mapping in structured output
- **AND** pipeline SHALL mark run as degraded unless strict materialization mode is enabled

#### Scenario: Existing monster file is preserved

- **WHEN** `modules/<slug>/monsters/<normalized_name>.json` already exists
- **THEN** materialization SHALL skip overwrite by default
- **AND** stage summary SHALL increment skipped-existing count


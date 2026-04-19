## MODIFIED Requirements

### Requirement: Successful ingest SHALL materialize or hydrate module monster stat files

After strict ingest success, the pipeline SHALL materialize monster stat files into `modules/<slug>/monsters/` from authoritative monster references so tabletop fail-closed combat can start encounters. Authoritative references MAY come from bestiary-backed seed data or authored module assets when seed artifacts are absent, and authorized non-bestiary monsters SHALL support controlled AI generation only after deterministic sources are exhausted.

#### Scenario: Seeded monster maps to bestiary entry

- **WHEN** `monsters_seed.json` contains a monster that resolves in `data/bestiary/monster_compendium.json`
- **THEN** pipeline SHALL create `modules/<slug>/monsters/<normalized_name>.json`
- **AND** created file SHALL include schema-compatible fields required by combat loader paths

#### Scenario: Seed artifact missing but authored module content references a monster

- **WHEN** `monsters_seed.json` is missing or empty
- **AND** authored module assets reference a monster identity in area or equivalent builder-owned content
- **THEN** materialization SHALL discover that monster from authored module content
- **AND** SHALL continue hydration without requiring seed regeneration first

#### Scenario: Authorized monster can be reused from deterministic source

- **WHEN** an authoritative monster reference does not already exist locally
- **AND** a trusted reusable monster JSON source exists for the normalized identity
- **THEN** materialization SHALL create the local module monster file from that deterministic source before considering AI generation

#### Scenario: Authorized non-bestiary monster uses controlled AI generation

- **WHEN** an authoritative monster reference has no deterministic reusable source and no bestiary match
- **AND** that monster is authorized by authored module content
- **THEN** materialization SHALL allow controlled AI generation for that monster
- **AND** successful generation SHALL create `modules/<slug>/monsters/<normalized_name>.json` with schema-compatible fields required by combat loader paths

#### Scenario: Authoritative monster hydration fails

- **WHEN** an authoritative monster reference cannot be satisfied by deterministic sources and controlled AI generation does not produce a valid local monster file
- **THEN** materialization SHALL report a structured unresolved hydration outcome for that monster
- **AND** pipeline SHALL mark the run as degraded unless strict materialization mode is enabled

#### Scenario: Existing monster file is preserved

- **WHEN** `modules/<slug>/monsters/<normalized_name>.json` already exists
- **THEN** materialization SHALL skip overwrite by default
- **AND** stage summary SHALL increment skipped-existing count

## MODIFIED Requirements

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

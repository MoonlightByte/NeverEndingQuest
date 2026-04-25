# homebrew-ingest-monster-materialization Specification Delta

## ADDED Requirements

### Requirement: Shared monster hydration SHALL reject schema-incomplete precedence wins
Shared monster hydration SHALL require schema sufficiency before accepting `existing`, `reuse`, or `bestiary` precedence outcomes as successful materialization.

#### Scenario: Schema-incomplete local existing file falls through to later recovery
- **GIVEN** `modules/<slug>/monsters/<normalized_name>.json` already exists
- **AND** that local file is missing one or more required hydration fields such as `size`, `alignment`, or `armorClass`
- **WHEN** shared monster materialization runs
- **THEN** the helper SHALL NOT return successful `existing` hydration solely because the file is present
- **AND** SHALL continue to later deterministic or controlled recovery paths.

#### Scenario: Schema-incomplete reusable candidate is skipped
- **GIVEN** a trusted reusable monster JSON exists in another module for the same normalized slug
- **AND** that reusable file is missing one or more required hydration fields
- **WHEN** shared monster materialization evaluates reuse-first hydration
- **THEN** the helper SHALL NOT copy that file into the target module
- **AND** SHALL continue to the next recovery path.

#### Scenario: Schema-incomplete compendium entry does not count as successful bestiary hydration
- **GIVEN** the normalized monster slug exists in `data/bestiary/monster_compendium.json`
- **AND** the matching entry is missing one or more required hydration fields
- **WHEN** shared monster materialization evaluates raw bestiary-backed copy
- **THEN** the helper SHALL NOT treat that entry as successful `bestiary` hydration
- **AND** SHALL fall through to controlled generation when generation is available.

#### Scenario: No schema-sufficient deterministic source fails closed when generation is unavailable
- **GIVEN** local existing, reusable, and compendium-backed candidates are all schema-incomplete or unavailable
- **AND** controlled generation is disabled
- **WHEN** shared monster materialization runs
- **THEN** the helper SHALL return a structured failure result
- **AND** SHALL NOT classify the monster as successfully hydrated.

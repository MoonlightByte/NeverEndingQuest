## ADDED Requirements

### Requirement: Monster fallback generation SHALL be explicit and monster-specific

When reusable monster media is unavailable, generation fallback SHALL remain opt-in and SHALL use monster-specific generation flow.

#### Scenario: Provider disabled

- **WHEN** prewarm runs without `--allow-provider`
- **AND** a monster has no reusable media
- **THEN** prewarm SHALL not call provider generation
- **AND** result SHALL report skipped/degraded for that entity

#### Scenario: Provider enabled

- **WHEN** prewarm runs with `--allow-provider`
- **AND** a monster has no reusable media
- **THEN** fallback generation SHALL run through monster generator tooling
- **AND** generation SHALL NOT route through character portrait prompt/service paths

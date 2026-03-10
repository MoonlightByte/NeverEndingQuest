## ADDED Requirements

### Requirement: Module builder SHALL emit a per-module NPC profile seed artifact

Module generation SHALL emit `npc_profile_seeds.json` under the generated module directory as an additive artifact.

The artifact SHALL include module-local NPC seed records for runtime materialization.

#### Scenario: Successful module generation with location NPCs
- **WHEN** module build completes for a module containing NPC entries in area locations
- **THEN** `modules/<module>/npc_profile_seeds.json` is created
- **AND** the file contains deterministic seed records keyed by canonical NPC identity

### Requirement: Seed records SHALL preserve canonical identity and source context

Each seed record SHALL preserve enough context to improve runtime materialization quality without requiring eager full-sheet generation.

Minimum record contract:
- `name`
- `aliases` (optional)
- `source_refs` (area/location references)
- `description` (if available)
- `attitude` (if available)

Optional profile hints:
- `race`, `class`, `background`, `level`
- `age`, `height`, `weight`, `eyes`, `skin`, `hair`

#### Scenario: Canonicalized NPC appears in multiple locations
- **WHEN** the same canonical NPC appears in multiple area/location entries
- **THEN** one canonical seed record is written
- **AND** `source_refs` includes all relevant occurrences

### Requirement: Seed generation SHALL be non-fatal to module build completion

Seed artifact creation failures SHALL not invalidate module build output.

#### Scenario: Seed write failure
- **WHEN** seed generation encounters an IO or serialization error
- **THEN** module build still completes
- **AND** failure is logged for operator visibility

### SHOULD Guidance

- Seed generation SHOULD run after NPC reconciliation so canonical names and aliases are stable.

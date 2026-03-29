## ADDED Requirements

### Requirement: Relationship edges use canonical PC identity keys
The live companion memory system MUST key relationship edges by canonical PC identity rather than raw display-name strings. The identity resolution path MUST treat naming variants, casing drift, and ordinary tabletop normalization differences as the same logical PC, and MUST prefer a stable `character_id` when one is available.

#### Scenario: Name variants map to one relationship edge
- **WHEN** the same PC appears across runtime surfaces as minor label variants such as case changes, spaces versus underscores, or similar canonicalized forms
- **THEN** the system MUST resolve those variants to one logical relationship-edge key instead of creating duplicate edges for the same PC

#### Scenario: Stable character identifier outranks label formatting
- **WHEN** a PC has both a stable `character_id` and one or more human-readable labels
- **THEN** the system MUST use the stable identity as the authoritative edge key and MUST NOT fragment relationship state when display labels change later

### Requirement: Canonical linking degrades safely when PC identity is incomplete
Canonical edge linking MUST fail soft when a specific PC identity cannot be resolved safely. An identity miss MUST NOT corrupt the companion packet, and single-player mode MUST remain valid without requiring multiplayer-specific metadata.

#### Scenario: Unresolved specific-PC identity falls back without corruption
- **WHEN** a meaningful companion event appears to be personal but the runtime cannot resolve a safe canonical PC identity for that event
- **THEN** the system MUST preserve valid companion continuity through group state or skip the personal edge update, and MUST NOT classify the packet as malformed solely because the PC key could not be resolved

#### Scenario: Single-player mode remains compatibility-safe
- **WHEN** the live runtime has only one active party member and no multiplayer-specific identity expansion is needed
- **THEN** the relationship-edge model MUST remain valid and MUST NOT require a separate storage backend or multiplayer-only data shape
# companion-memory-active-pc-projection Specification

## Purpose
TBD - created by archiving change tt-npc-memory-relationship-edges. Update Purpose after archive.
## Requirements
### Requirement: Narrator projection is active-PC-first and token-bounded
Narrator companion-memory projection MUST prioritize the active PC relationship edge when one exists. The projection MUST remain bounded by including at most one additional non-active relationship note, and only when that secondary note is high-signal and scene-relevant.

#### Scenario: Active PC receives the relevant relationship edge
- **WHEN** narrator context is assembled for a turn with an active PC and the companion NPC has a stored relationship edge for that PC
- **THEN** the projected companion-memory context MUST include the active PC edge rather than only a blended group summary

#### Scenario: Secondary relationship context remains tightly bounded
- **WHEN** a companion NPC has several non-active relationship edges in addition to the active PC edge
- **THEN** the narrator projection MUST include no more than one secondary high-signal note and MUST NOT dump all stored edges into the prompt

### Requirement: Sparse or degraded packets can still project bounded relationship continuity
Sparse or degraded companion memory packets that remain structurally valid MUST be able to project bounded relationship-edge continuity when such edge data exists. Truly malformed packets MUST remain excluded.

#### Scenario: Degraded packet still exposes bounded active-PC continuity
- **WHEN** a structurally valid companion packet is classified as degraded-extract but contains usable relationship-edge data for the active PC
- **THEN** narrator context assembly MUST preserve a bounded active-PC relationship note instead of dropping the companion to group-only amnesia

#### Scenario: Malformed packet remains excluded despite edge-aware projection logic
- **WHEN** a companion packet has unreadable structure or unsafe value shapes
- **THEN** the runtime MUST continue to exclude that packet from narrator injection rather than attempting edge-aware fallback on malformed data


# companion-memory-relationship-edges Specification

## Purpose
TBD - created by archiving change tt-npc-memory-relationship-edges. Update Purpose after archive.
## Requirements
### Requirement: Companion memory stores bounded group state and distinct per-PC relationship edges
The live companion memory system MUST persist both bounded NPC-global or group continuity state and additive per-PC relationship edges for companion NPCs. Per-PC relationship edges MUST allow one PC's trust, respect, fear, closeness, or resentment history to diverge from another PC's without overwriting the shared group-continuity view.

#### Scenario: Mixed companion feelings remain separated by PC
- **WHEN** a journal history shows a companion NPC resenting one PC for theft, coercion, or betrayal while respecting another PC for leadership, rescue, or battlefield support
- **THEN** the persisted companion memory state MUST retain distinct relationship-edge outcomes for those PCs instead of collapsing them into one blended emotional result

#### Scenario: Group-only beats remain available without forced personal attribution
- **WHEN** a journal entry describes the companion NPC traveling with the party, standing watch, or joining a party-wide battle without strong evidence tying the beat to one specific PC
- **THEN** the runtime MUST preserve that continuity in bounded NPC-global or group state and MUST NOT force the beat into an arbitrary per-PC edge

### Requirement: Relationship-edge attribution fails soft on ambiguity and supports multi-edge updates when evidence is explicit
The live companion memory writer MUST only assign per-PC relationship-edge updates when the narrative evidence is strong enough to support a specific PC linkage. Ambiguous entries MUST fail soft into group-only continuity, while entries with separate explicit evidence for multiple PCs MAY update multiple edges in one pass.

#### Scenario: Ambiguous relationship beat stays group-only
- **WHEN** a meaningful journal entry includes the companion NPC and the party but does not clearly tie the interaction to a specific PC
- **THEN** the system MUST preserve the event as valid continuity using group state and MUST NOT mark the packet malformed or invent a personal edge assignment

#### Scenario: One entry can update multiple relationship edges
- **WHEN** a single journal entry explicitly shows different PCs having different direct effects on the same companion NPC in that scene
- **THEN** the system MUST be able to update more than one relationship edge for that companion NPC from that entry while preserving any separate group-wide continuity


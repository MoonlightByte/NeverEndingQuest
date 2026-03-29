## Why

The first NPC memory hardening slice fixed parser brittleness and soft-fallback behavior, but it intentionally stopped before the main tabletop edge case: one companion NPC still carries a single blended relationship state for the whole party. In live multi-PC play, that causes trust, resentment, and respect earned by one PC to bleed across unrelated PCs, which is now the highest-value remaining continuity failure to fix before deeper `memory.db` work.

This change SHOULD deliver a narrow Phase 2A follow-up on the current file-backed runtime so active-PC narration can reflect per-PC relationship drift now, while the broader memory architecture and retrieval expansion move to `plans/version-2/memory.md`.

## What Changes

- MUST add additive per-PC companion relationship edges to the live file-backed NPC memory data model while preserving a bounded NPC-global/group state for shared continuity.
- MUST key relationship edges by canonical PC identity rather than display-name accidents so tabletop tabs, party membership drift, and future `character_id` adoption do not fragment memory state.
- MUST update the live journal-to-companion-memory path to attribute meaningful companion interactions to one or more PCs when the narrative evidence is strong enough, while preserving safe group-only fallback when attribution is ambiguous.
- MUST update narrator-facing projection so the active PC receives the relevant relationship edge, plus at most one additional high-signal tension/alliance note when scene-relevant.
- MUST keep malformed-data exclusion behavior for truly broken packets, and MUST keep sparse/degraded soft-fallback behavior from the earlier hardening slice.
- MUST provide rebuild and regression coverage for mixed-relationship cases such as one PC betraying or coercing an NPC while another PC earns trust or battlefield respect.
- MUST NOT require `memory.db` retrieval integration, Titan relationship analytics, or a full companion-memory subsystem rewrite in this slice.
- SHOULD treat this as the last planned expansion of the legacy file-backed companion-memory path before remaining memory evolution shifts to the version-2 architecture plan.

## Capabilities

### New Capabilities
- `companion-memory-relationship-edges`: The live companion memory system stores additive per-PC relationship edges alongside a bounded NPC-global/group state so one PC's social history does not overwrite another's.
- `companion-memory-canonical-pc-linking`: Relationship edges use canonical PC identity keys and survive ordinary tabletop naming variation, active-PC switching, and future-safe identity migration.
- `companion-memory-active-pc-projection`: Narrator companion-memory projection includes the active PC edge and only tightly bounded secondary edge context when relevant.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `core/memories/action_parser.py`
  - `core/memories/companion_memory.py`
  - `scripts/memory_management/compress_memories.py`
  - `core/ai/conversation_utils.py`
  - companion-memory regression/rebuild scripts under `scripts/`
- Affected systems:
  - file-backed companion memory extraction and persistence
  - compressed companion memory packets
  - narrator companion-memory prompt injection in tabletop sessions
  - operator rebuild/recovery flow for existing saves
- Merge-safety impact:
  - MUST remain additive and SHOULD prefer extension-style logic over structural host rewrites; any required host edits MUST be marked `# TABLETOP MODE:`.
- SP/MP compatibility impact:
  - MUST preserve single-player behavior.
  - MUST improve multi-PC tabletop continuity without requiring a separate storage backend.
- Rollout risks:
  - attribution heuristics may over-assign an event to the wrong PC,
  - per-PC edge payloads may widen prompt packets if not tightly bounded,
  - legacy saves may need rebuilds to realize the new edge model.
- Fallback strategy:
  - ambiguous events SHOULD update only NPC-global/group continuity,
  - malformed packets MUST still be excluded,
  - sparse/degraded packets MUST continue using bounded fallback projection,
  - if edge attribution proves too noisy, the runtime SHOULD be able to project only group state while preserving stored edge data for later refinement.
- Explicit non-goals:
  - `memory.db` relationship retrieval,
  - Titan alignment/relationship scoring,
  - full enhanced-parser runtime migration,
  - unbounded per-PC memory packets in narrator prompts,
  - universal replacement of the legacy file-backed companion-memory stack.

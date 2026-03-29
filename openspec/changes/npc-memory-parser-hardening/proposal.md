## Why

The live companion NPC memory system currently over-promises and under-delivers for rich tabletop relationships. In practice, important journaled events can increment an NPC's interaction count without producing any crystallized memories, emotional state, or reliable future continuity, and the runtime then suppresses that NPC from narrator context as if the data were corrupted.

This needs to be fixed now because companion continuity is a high-visibility player experience issue, and the current failure mode is already reproducible with real gametest data. The first slice should harden the existing file-backed runtime path without waiting for later `memory.db` retrieval work.

## What Changes

- Harden the live companion memory extraction path so generalized social, coercion, recruitment, watch/escort, and combat-teamwork journal phrasing can produce meaningful NPC memory signals.
- Separate mention counting from meaningful interaction accounting so the runtime can distinguish "NPC was present" from "NPC had relationship-shaping actions."
- Classify companion memory packets as healthy, sparse, degraded-extract, or malformed instead of treating all zero-memory packets as corruption.
- Add a bounded soft-fallback narrator packet for sparse or degraded companion memories so valid NPCs are not dropped from context wholesale.
- Preserve the current file-backed companion memory flow and compressed prompt injection path for the testing branch.
- Add focused regression coverage using real narrative-style journal excerpts representative of companion NPC play.
- MUST NOT require `memory.db` companion retrieval integration in this slice.
- MUST NOT yet implement per-PC relationship edges in this slice; that follow-up remains a separate tabletop change.

## Capabilities

### New Capabilities
- `companion-memory-extraction-hardening`: The live companion memory parser recognizes broader relationship-shaping journal events and records meaningful interaction signals without relying on narrow exact phrasing.
- `companion-memory-quality-classification`: The runtime distinguishes healthy, sparse, degraded-extract, and malformed companion memory packets and only treats truly malformed packets as corruption.
- `companion-memory-soft-context-fallback`: Sparse or degraded companion memories project a bounded continuity fallback into narrator context instead of excluding the NPC entirely.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `core/memories/action_parser.py`
  - `core/memories/companion_memory.py`
  - `scripts/memory_management/compress_memories.py`
  - `core/ai/conversation_utils.py`
  - companion memory regression scripts under `scripts/`
- Affected systems:
  - file-backed companion memory extraction
  - compressed companion memory packet generation
  - narrator companion-memory injection
  - operator rebuild/diagnostic expectations for degraded companion state
- Merge-safety impact:
  - SHOULD remain additive and preserve existing upstream-compatible host behavior, with any required host edits marked `# TABLETOP MODE:`.
- SP/MP compatibility impact:
  - MUST preserve single-player behavior.
  - MUST improve TABLETOP MODE companion continuity without requiring a multiplayer-only code path.
- Risks:
  - broader parser patterns may overmatch,
  - fallback packets may become noisy if not tightly bounded,
  - quality classification may hide real data corruption if criteria are too soft.
- Fallback strategy:
  - keep malformed-data exclusion for truly invalid packets,
  - use bounded sparse/degraded fallback packets for otherwise valid NPCs,
  - keep the existing file-backed flow intact if richer extraction does not trigger for a given entry.
- Non-goals for this change:
  - `memory.db` companion retrieval integration,
  - full runtime adoption of the enhanced parser/crystallizer stack,
  - per-PC relationship edges,
  - LLM-based freeform memory extraction in the live turn loop.

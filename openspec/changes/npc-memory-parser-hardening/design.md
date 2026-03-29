## Context

The live companion memory runtime is currently file-backed and flows through four key stages:

1. `core/ai/cumulative_summary.py` appends a journal entry and invokes companion memory processing.
2. `core/memories/companion_memory.py` uses `ActionParser` and `MemoryCrystallizer` to derive per-NPC memory files.
3. `scripts/memory_management/compress_memories.py` projects those files into `data/companion_memories/memories_compressed.json`.
4. `core/ai/conversation_utils.py` injects the compressed packet into narrator context, but currently excludes NPCs whose packet looks invalid.

Recent gametest evidence shows a recurring failure mode: an NPC can accumulate positive interaction count with zero emotional state and zero crystallized memories, then be excluded from prompt context as "corrupted." The supplied Blarg journal excerpts demonstrate that this can happen even when the journal contains multiple relationship-shaping beats. The root issue is not one malformed save file; it is a mismatch between brittle extraction heuristics and the stronger continuity promise implied by companion NPC UX.

This first slice targets the current testing branch, not the later `memory.db` retrieval architecture. It must preserve the live file-backed path, keep prompt packets bounded, and avoid prematurely taking on per-PC relationship edges.

Stakeholders:

- players and facilitators who expect companion NPCs to remember meaningful social and combat interactions,
- runtime systems that need bounded, narrator-friendly continuity packets,
- future memory architecture work that will eventually integrate richer retrieval without regressing current play.

## Goals / Non-Goals

**Goals:**

- MUST harden the live companion memory extraction path so broader narrative phrasing can produce meaningful memory signals.
- MUST distinguish story presence from meaningful relationship interaction.
- MUST classify companion memory packets more accurately so sparse but valid NPCs are not mislabeled as corrupted.
- MUST preserve narrator continuity for sparse or degraded companion memories through a bounded fallback packet.
- MUST remain compatible with the current file-backed runtime path and current compressed memory injection flow.
- SHOULD keep the implementation additive so the later per-PC-edge follow-up can build on the same quality model.

**Non-Goals:**

- MUST NOT require `memory.db` retrieval integration.
- MUST NOT implement per-PC relationship edges in this change.
- MUST NOT replace the entire companion memory subsystem with a new architecture.
- MUST NOT add live-turn LLM-based freeform memory extraction.
- SHOULD NOT widen narrator prompt payloads beyond a small bounded continuity projection.

## Decisions

### Decision 1: Preserve the existing file-backed runtime as the authority for this slice

The first slice will keep the existing runtime path (`journal -> companion memory files -> compressed packet -> narrator injection`) rather than jumping directly to `memory.db` retrieval or a full enhanced-stack migration.

Rationale:

- This is the shortest path to fixing the live user-facing failure.
- It keeps the testing branch low-risk and bounded.
- It avoids entangling current gametest repairs with v2 retrieval architecture.

Alternatives considered:

- Migrate companion memory directly into `memory.db` now.
  - Rejected for this slice because it increases schema, retrieval, migration, and prompt-assembly scope.
- Replace the live runtime immediately with the enhanced parser/crystallizer path.
  - Deferred because the enhanced path is not yet established as the active runtime and would add avoidable risk.

### Decision 2: Introduce explicit memory-quality states

The runtime will classify companion memory packets into explicit quality states such as `healthy`, `sparse`, `degraded_extract`, and `malformed`.

Rationale:

- The current binary rule collapses several very different situations into "corrupted."
- Operators and runtime consumers need to distinguish parser weakness from true data breakage.
- This quality layer creates a safe bridge to later richer relationship models.

Alternatives considered:

- Keep the current binary corruption heuristic and only widen parser patterns.
  - Rejected because parser misses will still look like corruption.
- Stop validating memory packets entirely.
  - Rejected because malformed files still need protection.

### Decision 3: Split mention accounting from meaningful interaction accounting

The runtime will separately track NPC mention/story presence and parser-confirmed meaningful relationship interactions.

Rationale:

- A journal entry can mention an NPC without changing the relationship.
- Current counters overstate actual memory success and drive false corruption classification.
- Separate counters improve observability and allow better regression assertions.

Alternatives considered:

- Keep one counter and reinterpret it downstream.
  - Rejected because a single ambiguous counter remains misleading.

### Decision 4: Add a bounded soft-fallback narrator packet for sparse/degraded NPCs

When an NPC is valid but lacks strong crystallized output, the narrator should receive a compact continuity fallback rather than no packet at all.

Rationale:

- Total exclusion causes the NPC to feel absent or reset.
- A bounded fallback preserves continuity while acknowledging lower confidence.
- This keeps prompt cost controlled and avoids inventing unsupported details.

Expected fallback content:

- NPC name and party role if known,
- memory quality marker,
- minimal recent continuity summary derived from available structured state,
- no unsupported fine-grained emotional claims.

Alternatives considered:

- Always exclude sparse packets.
  - Rejected because it creates false amnesia.
- Dump larger journal-derived fallback text into prompts.
  - Rejected because it risks prompt bloat and narrative contamination.

### Decision 5: Harden the current parser before promoting enhanced runtime modules

This slice will widen and organize the current parser's semantic families while keeping the enhanced parser/crystallizer path out of the live runtime for now.

Rationale:

- It directly addresses the observed bug in the active code path.
- It is easier to regression-test with the current scripts.
- It keeps the change bounded and merge-safe.

Alternatives considered:

- Promote `enhanced_action_parser.py` and `enhanced_memory_crystallizer.py` immediately.
  - Deferred because that belongs in a later unification pass once this slice stabilizes the live contract.

## Risks / Trade-offs

- [Broader parser patterns overmatch narrative text] -> Mitigation: require context windows, use excerpt-driven regression fixtures, and bias toward relationship-significant families rather than broad generic verbs.
- [Sparse fallback packets become noisy or misleading] -> Mitigation: keep fallback fields bounded, explicitly tag memory quality, and avoid unsupported emotional claims.
- [New counters and quality fields drift from existing compression expectations] -> Mitigation: keep new fields additive, preserve backward-compatible top-level data, and update compressor/consumer code in the same slice.
- [Real malformed packets become hidden under softer classification] -> Mitigation: reserve `malformed` for wrong shapes/unreadable values and keep hard exclusion for that class only.
- [Future per-PC-edge work must redo this slice] -> Mitigation: design quality states and counter semantics so they remain valid when relationship edges are added later.

## Migration Plan

1. Add parser coverage and explicit counter/quality semantics to the file-backed companion memory writer.
2. Update compressed output generation to preserve any new quality/accounting fields needed by narrator consumers.
3. Update narrator injection to classify packets and project soft fallback context for sparse/degraded NPCs.
4. Add regression fixtures using real narrative-style journal excerpts, including the known Blarg failure mode.
5. Rebuild affected companion memory files on test saves using the existing refresh flow or a narrow rebuild path if needed.

Rollback strategy:

- Code rollback is straightforward because the slice is file-backed and additive.
- If the new parser overmatches, revert to the previous parser rules and classification behavior while keeping existing save files intact.
- If fallback packets prove noisy, disable fallback projection and retain improved classification semantics until a narrower projection is ready.

## Open Questions

- Should `degraded_extract` require a dedicated persisted field, or can it be derived from existing counts at load time?
- Should the compressed packet carry only quality state, or also carry the split counters for observability?
- Should sparse fallback continuity be derived purely from structured counters/roles, or is a tiny recent-excerpt projection acceptable in this slice?
- Should the rebuild path for this slice remain manual/scripted, or should operator-facing diagnosis helpers be included immediately?

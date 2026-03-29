## Context

The first NPC memory hardening slice repaired three major issues in the live file-backed companion memory path:

1. broader extraction coverage for relationship-significant events,
2. split accounting for story presence versus meaningful interaction,
3. quality classification plus sparse/degraded narrator fallback.

That slice deliberately did not add per-PC relationship edges. As a result, the current live runtime still stores one blended emotional state per companion NPC. In tabletop play, this causes an NPC's feelings about one PC to leak onto other PCs even when the journal clearly supports different relationships.

The active runtime path remains:

1. `core/ai/cumulative_summary.py` appends journal entries and triggers companion memory processing.
2. `core/memories/companion_memory.py` derives per-NPC file-backed memory state.
3. `scripts/memory_management/compress_memories.py` projects those files into compressed narrator-facing packets.
4. `core/ai/conversation_utils.py` injects bounded companion context into narrator prompts.

This design MUST keep that path as the authority for this change. The broader retrieval architecture in `plans/version-2/memory.md` remains the long-term destination, but this slice addresses the remaining live tabletop continuity bug before the project moves memory evolution to v2.

Stakeholders:

- facilitators running multi-PC tabletop sessions,
- players who expect NPCs to react differently to different PCs,
- runtime systems that need bounded prompt packets,
- future v2 memory work that needs a clean handoff instead of another large legacy rewrite.

## Goals / Non-Goals

**Goals:**

- MUST add additive per-PC companion relationship edges to the current file-backed runtime.
- MUST preserve a bounded NPC-global or group-continuity state for events that belong to the whole party.
- MUST attribute edge updates only when the journal evidence is strong enough to support a specific PC association.
- MUST keep narrator projection bounded by prioritizing the active PC edge and at most one additional high-signal secondary note.
- MUST preserve healthy/sparse/degraded/malformed quality semantics from the prior hardening slice.
- MUST support deterministic rebuild of existing saves from `journal.json`.
- SHOULD make the resulting data model easy to map into a future `memory.db` relationship-event design.

**Non-Goals:**

- MUST NOT introduce `memory.db` retrieval into live narration.
- MUST NOT replace the current live file-backed companion memory path with a new architecture.
- MUST NOT depend on LLM-based freeform extraction in the turn loop.
- MUST NOT dump all relationship edges into prompts.
- MUST NOT attempt Titan relationship scoring, provenance expansion, or global retrieval ranking in this slice.
- SHOULD NOT continue expanding the legacy file-backed memory path beyond this narrow Phase 2A follow-up.

## Decisions

### Decision 1: Keep the legacy file-backed runtime as the implementation surface for Phase 2A

This change will extend the current `journal -> companion memory file -> compressed packet -> narrator injection` flow instead of jumping to v2 retrieval work.

Contract layer:
- The live file-backed path MUST remain the source of truth for this slice.
- The change MUST be additive so existing companion memory files can be rebuilt rather than migrated through a complex one-off transformer.
- The project SHOULD move any deeper memory evolution after this slice into `plans/version-2/memory.md`.

Rationale:
- This fixes the active gameplay issue in the currently-used path.
- It avoids blocking on `memory.db` prompt-plane integration work that is explicitly sequenced later.
- It gives v2 a cleaner handoff point: the legacy path becomes "good enough and stable," not "still missing the core tabletop edge case."

Alternatives considered:
- Move relationship edges directly into `memory.db` now.
  - Rejected because it would entangle prompt-plane hygiene, retrieval ranking, schema migrations, and live narrator integration in one step.
- Keep the blended state until v2.
  - Rejected because the main tabletop continuity failure would remain live and visible.

### Decision 2: Split companion memory state into `npc_global_state` and `relationship_edges`

The per-NPC file-backed memory model will carry both:
- `npc_global_state`: shared party-facing continuity and overall disposition,
- `relationship_edges`: per-PC edge state keyed by canonical identity.

Contract layer:
- `npc_global_state` MUST remain available for group beats, party reputation, and ambiguous events.
- `relationship_edges` MUST be additive and MUST NOT replace the global state entirely.
- Edge fields MUST remain bounded to a compact set of reusable dimensions: trust, respect, intimacy/closeness, fear/caution, resentment, recent triggers, and last significant interaction timestamp.

Guidance layer:
- The legacy top-level `current_emotional_state` MAY remain as a backward-compatible mirror during the transition, but the new structure SHOULD become the authoritative writer surface for new logic.
- `resentment` SHOULD be explicit on edges because it captures betrayal pressure that does not map cleanly onto the existing five-vector model.

Rationale:
- Some events are truly group-wide and should not be force-attributed to one PC.
- Some events are clearly personal and should not bleed across the party.
- This dual model matches the phased plan already outlined in `plans/npc-memory.md`.

Alternatives considered:
- Per-PC edges only, no global state.
  - Rejected because ambiguous or party-wide events would require unsafe forced attribution.
- Global state with edge deltas only in prompt assembly.
  - Rejected because the state would still be lossy at persistence time.

### Decision 3: Use evidence-gated attribution with fail-soft group fallback

Relationship edge updates will only be written when the journal contains strong evidence tying the companion interaction to one or more specific PCs.

Contract layer:
- Explicit named interaction, confrontation, rescue, betrayal, command-following, or direct social exchange MUST be eligible for per-PC edge attribution.
- Ambiguous teamwork, group travel, or scene-presence beats MUST fall back to `npc_global_state` rather than guessing a specific PC owner.
- A single journal entry MAY update multiple relationship edges if separate PC-specific evidence exists in that same entry.
- Ambiguous attribution MUST fail soft by preserving global continuity and MUST NOT mark the packet malformed.

Guidance layer:
- Attribution SHOULD use canonicalized party member names and local context windows around companion mentions.
- The parser SHOULD prefer direct verbs and nearby names over broad whole-entry heuristics.
- If an event names the active PC but not other PCs, the system SHOULD treat that as strong attribution.

Rationale:
- The highest risk in this slice is over-assigning feelings to the wrong PC.
- Group fallback protects continuity without inventing personal edges.
- Multiple explicit edge updates in one entry are necessary for mixed cases like one PC coercing an NPC while another earns respect.

Alternatives considered:
- Force every meaningful event onto the active PC.
  - Rejected because journal summaries may describe multiple PCs and off-turn continuity.
- Never assign personal edges from journal text.
  - Rejected because that would not solve the tabletop bug.

### Decision 4: Canonical edge keys must be stable and future-safe

Relationship edges will use canonical PC identity keys, not raw display names.

Contract layer:
- The writer MUST resolve edge keys through a stable normalization path.
- Preferred identity order MUST be: `character_id` when available, otherwise canonical normalized character name.
- Naming variants, casing drift, and underscore/space differences MUST resolve to the same logical edge.
- In single-player mode, the system MUST remain valid when only one canonical PC exists.

Guidance layer:
- This slice SHOULD reuse existing tabletop identity helpers and normalization patterns already used in party and character routing.
- The stored edge payload MAY include a display-name hint for diagnostics, but the key itself SHOULD remain canonical.

Rationale:
- Name drift is common in this codebase and already handled elsewhere.
- Future v2 identity migration becomes easier if the live edge model already prefers stable keys.

Alternatives considered:
- Store edges by visible character name only.
  - Rejected because future rename drift would fragment edge state.

### Decision 5: Narrator projection stays active-PC-first and token-bounded

Prompt projection will surface relationship edges only when they materially help the current scene.

Contract layer:
- The active PC edge MUST be projected when available.
- At most one additional non-active edge summary MAY be projected, and only when it is high-signal and scene-relevant.
- Sparse and degraded packets with valid edge data MUST still be able to project bounded edge continuity.
- Malformed packets MUST remain excluded.

Guidance layer:
- Secondary notes SHOULD be limited to strongest tension or strongest alliance, not both.
- Projection SHOULD use compact human-readable summaries derived from stored edge state and recent triggers, not raw full edge objects.

Rationale:
- The goal is better continuity, not a wider prompt packet.
- Active-PC-first matches how tabletop turns are narrated.

Alternatives considered:
- Dump all edges into the prompt.
  - Rejected for token cost and confusion.
- Hide edge data unless packet quality is healthy.
  - Rejected because degraded but valid relationship signals are still useful.

### Decision 6: Rebuild and observability are part of the change, not a postscript

Existing saves will not automatically gain edge history without a rebuild from `journal.json`.

Contract layer:
- The refresh/rebuild flow MUST be documented and regression-tested.
- Logging MUST distinguish malformed-packet exclusion, ambiguous group fallback, and successful per-PC attribution.
- The implementation SHOULD make targeted tests easy for mixed-relationship excerpts.

Guidance layer:
- Diagnostics SHOULD expose whether a beat was stored as global-only or edge-attributed.
- Recovery docs SHOULD tell operators when a rebuild is needed after deployment.

Rationale:
- Without explicit rebuild and observability, operators cannot tell whether the new behavior is working or whether old files are still stale.

Alternatives considered:
- Leave rebuild as manual tribal knowledge.
  - Rejected because it will hide the value of the change in existing saves.

## Risks / Trade-offs

- [Specific-PC attribution overmatches and writes the wrong edge] -> Mitigation: require strong evidence gates, prefer local context windows, and fall back to `npc_global_state` on ambiguity.
- [Per-PC edge payload widens narrator context] -> Mitigation: active-PC-first projection, at most one secondary note, no raw edge dump.
- [Legacy data shape becomes awkward during transition] -> Mitigation: additive fields, backward-compatible mirrors where needed, and deterministic rebuild path.
- [Current parser abstractions are too coarse for fine relationship attribution] -> Mitigation: keep this slice narrow, extend only the active path, and defer deeper parser architecture changes to v2.
- [Operators mistake stale pre-change files for logic failure] -> Mitigation: document rebuild requirements and log edge/global attribution outcomes clearly.
- [This invites more legacy-stack expansion] -> Mitigation: explicitly treat this as the last planned Phase 2A fix before memory evolution moves to v2.

## Migration Plan

1. Extend the live companion-memory writer to persist `npc_global_state`, `relationship_edges`, and any compact attribution metadata needed for compression/projection.
2. Add canonical PC identity resolution support to the writer and rebuild flows.
3. Update extraction/accounting logic so meaningful events can be stored as edge-attributed, global-only, or mixed depending on evidence strength.
4. Update compressed projection and narrator injection to surface active-PC-first relationship summaries while preserving existing quality classification behavior.
5. Add regression fixtures for mixed-edge scenarios and document the rebuild path for existing saves.
6. After this slice stabilizes, move remaining memory evolution planning to `plans/version-2/memory.md` instead of extending the file-backed stack further.

Rollback strategy:

- Code rollback is straightforward because this slice is additive and file-backed.
- If attribution proves too noisy, projection can fall back to global-only summaries while preserving stored edge fields.
- If the new fields destabilize downstream readers, rebuild packets can temporarily ignore `relationship_edges` and continue using the prior hardening behavior.

## Open Questions

- Should the legacy top-level `current_emotional_state` remain a first-class mirrored field for compatibility, or become a derived view from `npc_global_state`?
- Should `recent_triggers` live only on relationship edges, or also on `npc_global_state` for group-wide tension summaries?
- Is the current journal summary format rich enough to support direct attribution in most real sessions, or will some lightweight upstream summary enrichment be needed later?
- Should diagnostics expose a dedicated counter for `group_only_meaningful_events` versus edge-attributed events, or is logging sufficient for Phase 2A?

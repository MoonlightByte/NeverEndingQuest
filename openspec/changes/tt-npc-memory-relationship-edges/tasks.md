## 1. Identity and Data Model Groundwork

- [x] 1.1 Audit the live companion-memory writer and rebuild scripts to identify where party-member identity is available today and where canonical PC identity resolution must be added (`core/memories/companion_memory.py`, `core/ai/cumulative_summary.py`, `scripts/memory_management/refresh_memories.py`, `core/memories/initialize_memories.py`).
- [x] 1.2 Add additive companion-memory data structures for `npc_global_state`, `relationship_edges`, and any bounded attribution metadata needed for rebuild/compression while preserving backward-compatible existing fields.
- [x] 1.3 Implement canonical PC identity helpers for relationship-edge keys using stable routing preference (`character_id` when available, otherwise normalized PC name) and verify naming-drift safety against current tabletop identity conventions.

## 2. Relationship Attribution and Persistence

- [x] 2.1 Extend the live journal processing path so companion memory extraction can receive or derive the party-member identity set needed for per-PC attribution without breaking single-player mode.
- [x] 2.2 Implement evidence-gated attribution logic that writes edge updates only for strong specific-PC signals and falls back to group-only continuity on ambiguity.
- [x] 2.3 Support mixed-entry handling where one journal entry can update multiple relationship edges plus shared group continuity when distinct PC-specific evidence exists.
- [x] 2.4 Preserve quality classification semantics so healthy, sparse, degraded-extract, and malformed outcomes continue to behave correctly after relationship-edge persistence is introduced.

## 3. Compression and Narrator Projection

- [x] 3.1 Update companion-memory compression output to preserve the bounded relationship-edge data required by narrator consumers without dumping raw full edge objects.
- [x] 3.2 Update narrator companion-memory projection in `core/ai/conversation_utils.py` so active-PC edge context is included when available and at most one secondary high-signal note is emitted when relevant.
- [x] 3.3 Ensure sparse and degraded packets can still project bounded active-PC relationship continuity while malformed packets remain excluded.
- [x] 3.4 Verify single-player behavior remains compatibility-safe by falling back to valid group or sole-PC projection without requiring multiplayer-only payload shape.

## 4. Recovery, Diagnostics, and Regression Coverage

- [x] 4.1 Update rebuild and recovery tooling/docs so existing saves can regenerate companion memories with relationship edges from `journal.json` and operators know when a rebuild is required.
- [x] 4.2 Add regression fixtures for mixed-relationship edge cases, including betrayal/coercion against one PC, earned trust/respect for another PC, ambiguous group-only teamwork, and canonical-name drift.
- [x] 4.3 Add focused tests covering canonical edge linking, group-only fallback on ambiguity, multi-edge updates from one entry, and active-PC-first narrator projection.
- [x] 4.4 Add observability assertions or diagnostics verifying whether a beat was stored as group-only continuity versus a specific relationship-edge update.

## 5. Verification and Handoff Boundary

- [x] 5.1 Run targeted verification for all touched files, including Python compile checks and the companion-memory regression suite.
- [x] 5.2 Perform a rebuild-oriented smoke pass on representative companion memory data to confirm the new edge model survives refresh/compression/projection end-to-end.
- [x] 5.3 Update plan notes or implementation documentation to state that deeper relationship retrieval, scoring, and broader memory evolution move to `plans/version-2/memory.md` after this Phase 2A slice stabilizes.

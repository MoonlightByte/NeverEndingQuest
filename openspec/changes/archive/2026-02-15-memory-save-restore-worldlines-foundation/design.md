## Context

The current save/restore model is JSON-first and already supports practical branch-and-replay play patterns. The new memory foundation adds durable SQLite storage (`data/memory.db`) and portability helpers, but save slots do not yet include memory DB state by default.

Without parity, restore can rewind JSON gameplay state while leaving memory DB in a future state, creating timeline drift. This design adds snapshot parity and explicit worldline lineage metadata while preserving merge safety, additive behavior, and existing SP/MP runtime contracts.

## Goals / Non-Goals

**Goals:**
- Make memory DB part of save/restore snapshot semantics.
- Keep restore deterministic and safe (no JSON/DB divergence on success).
- Add explicit worldline lineage metadata for forked timelines.
- Reuse existing portability and save-manager architecture.
- Keep behavior backward-compatible for legacy saves.

**Non-Goals:**
- Live narrator/combat memory retrieval injection.
- In-DB multi-world query partitioning in this phase.
- New gameplay UI for branch graph visualization.

## Decisions

1. **Snapshot-isolated Many Worlds model**
   - Decision: Use per-save memory package snapshots instead of a single shared DB with `worldline_id` filtering.
   - Rationale: Matches existing JSON save semantics and minimizes retrieval complexity before live LLM integration.
   - Alternative considered: single DB with branch IDs and query filters; rejected for higher correctness and migration risk.

2. **Integrate via SaveGameManager, not new runtime service**
   - Decision: Add hooks in `updates/save_game_manager.py` save/restore methods.
   - Rationale: Existing action handlers and web paths already delegate here; this keeps one control plane.
   - Alternative considered: standalone restore script path; rejected due to duplicate orchestration.

3. **Use portability helpers as the canonical snapshot transport**
   - Decision: Save flow uses portability export; restore uses portability import.
   - Rationale: Reuses manifest/hash validation and keeps storage operations consistent.
   - Alternative considered: raw sqlite file copy; rejected for WAL consistency and validation limitations.

4. **Fork-on-first-save-after-restore behavior**
   - Decision: After any restore, the next save gets a new `worldline_id` and parent linkage.
   - Rationale: Makes divergent trajectories explicit and deterministic with no ambiguity.
   - Alternative considered: continue same worldline when restore target is current head; rejected as harder to reason about and test.

5. **Deterministic legacy-save fallback**
   - Decision: If restoring a legacy save without memory package, initialize a clean DB state and annotate restore metadata with fallback mode.
   - Rationale: Prevents accidental carry-forward of stale/future memories.
   - Alternative considered: keep existing DB unchanged; rejected because it violates snapshot parity.

6. **Restore preflight validation before file mutations**
   - Decision: Validate memory package integrity/compatibility before backup, cleanup, or gameplay file overwrite in restore path.
   - Rationale: Prevents partial restore outcomes where JSON files are rewritten before memory-package failure is detected.
   - Alternative considered: validate after restore copy; rejected due to non-atomic failure semantics.

7. **Managed package import as single handling path**
   - Decision: Exclude `memory_db_package/` from generic restore file copy and handle package only via portability import helpers.
   - Rationale: Prevents stray runtime artifacts and keeps one canonical import path.
   - Alternative considered: copy package and import from copied location; rejected for unnecessary duplication and drift risk.

## Risks / Trade-offs

- [Restore failures from corrupt or missing package] -> Validate package before finalizing restore; fail restore for corrupt package, deterministic fallback only for known legacy saves.
- [Partial restore on validation failure] -> Run memory package preflight validation before any restore mutations.
- [Performance overhead on save] -> Snapshot export is bounded to one DB artifact and manifest; acceptable compared to full file copy save path.
- [Lineage metadata drift] -> Keep lineage generation in one save manager path and test restore->save branching explicitly.
- [Operator confusion during transition] -> Include package/fallback status in save metadata and save listing outputs.

## Migration Plan

1. Add memory package export hook to save creation flow and write package status into `save_metadata.json`.
2. Add memory package preflight + import hook to restore flow before restart completion.
3. Add deterministic legacy-save fallback path and annotate restore metadata.
4. Exclude `memory_db_package/` from generic restore copy loop and keep managed import single-path.
5. Add worldline metadata generation and post-restore fork context handling.
6. Add tests for parity, failure behavior, preflight atomicity, package-copy exclusion, and branch lineage invariants.
7. Rollback plan: disable memory package hooks while preserving JSON save/restore behavior.

## Open Questions

- Should fallback mode for legacy saves optionally trigger a guided backfill prompt, or remain strictly cold-start DB initialization?
- Should worldline metadata be mirrored in a global index file for faster branch graph inspection, or remain save-local only in this phase?

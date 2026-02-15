## Why

The JSON save/restore pipeline already supports practical branch-and-replay gameplay, but `data/memory.db` is currently outside that contract. Restoring a prior save can leave memory DB state ahead of restored JSON state, which breaks timeline coherence before live memory retrieval is wired into gameplay LLM paths.

## What Changes

- Add memory DB snapshot parity to the existing save/restore contract so each save captures JSON state and memory DB state together.
- Integrate memory DB package export during save and package import during restore using existing portability helpers.
- Add restore preflight validation so package failures fail before gameplay file mutations.
- Keep `memory_db_package/` out of generic restore file copy and route package handling through one managed import path.
- Define deterministic behavior for legacy saves that do not contain memory packages.
- Add worldline metadata to save metadata so branch lineage is explicit after restore-and-replay flows.
- Add branch-integrity tests for rewind/fork scenarios (save A -> diverge -> restore A -> new branch).
- Non-goals:
  - No live narrator/combat retrieval integration in this change.
  - No new gameplay UI for branch visualization.
  - No in-DB multi-world query model in this phase.
- Rollout risk and fallback:
  - Risk: restore failure if memory package is missing or corrupt.
  - Fallback: deterministic legacy-save path (re-init and optional rehydrate/backfill policy) instead of retaining stale DB state.
  - Keep additive, merge-safe host hooks and preserve SP/MP compatibility.

## Capabilities

### New Capabilities
- `memory-save-restore-parity`: save and restore workflows include memory DB snapshots as first-class save artifacts.
- `memory-worldline-branching`: save metadata tracks lineage (`worldline_id`, parent/fork origin) and enforces fork-on-first-save-after-restore behavior.

### Modified Capabilities
- `memory-db-portability`: portability contracts now include integration requirements for SaveGameManager-driven snapshot export/import and strict restore safety semantics.

## Impact

- Affected code:
  - `updates/save_game_manager.py`
  - `scripts/backfill_memory_db.py` (if shared import/export pathways are reused)
  - `core/memory/memory_portability.py` (integration and safety semantics)
  - save metadata producers/consumers in save listing and restore flows
- Data/storage:
  - Per-save memory package directory under each save folder
  - Extended `save_metadata.json` lineage fields
- APIs/contracts:
  - Save/restore contract includes memory package parity
  - Legacy save restore behavior is explicit and deterministic
- Compatibility:
  - Additive change with backward-compatible legacy-save fallback
  - Single-player and tabletop multiplayer modes both use same save contract

## Why

Current gameplay paths for recruiting NPC allies and promoting NPC -> PC are functional, but module-authored NPC intent is not consistently carried into runtime NPC materialization.

Today, many NPC sheets are generated late with minimal context. This can produce generic outputs, occasional name/canonical drift, and profile-readiness gaps that later flows must patch.

Phase 1 should establish a deterministic alignment layer between:
- module-generation NPC intent,
- runtime NPC sheet materialization,
- and promotion/profile-readiness contracts.

## What Changes

- Add a per-module NPC seed contract file (`npc_profile_seeds.json`) generated during module build.
- Extend `core/generators/npc_builder.py` to accept module seed context and apply deterministic postprocessing.
- Align runtime materialization callers (`core/ai/action_handler.py`, `core/generators/combat_builder.py`) to pass seed context when creating/loading NPC sheets.
- Harden Add Existing candidate classification so explicit NPC records are not surfaced as player candidates.
- Add regression coverage for seed generation, runtime alignment, and promotion compatibility.

### Non-goals

- No full toolkit UI rebuild in this phase.
- No async worker/job queue introduction.
- No broad provider routing migration across all toolkit paths.
- No eager generation of full NPC sheets for every module NPC by default.

## Capabilities

### New Capabilities
- `module-builder-npc-seed-contract`: module generation produces a deterministic NPC profile seed artifact for runtime use.
- `module-builder-runtime-npc-materialization-alignment`: runtime NPC materialization uses module seed context and enforces role/profile consistency.

### Modified Capabilities
- Existing Add Existing candidate listing behavior is tightened for explicit NPC classification.

## Impact

- Affected code:
  - `core/generators/module_builder.py`
  - `core/generators/npc_builder.py`
  - `core/ai/action_handler.py`
  - `core/generators/combat_builder.py`
  - `web/routes/tabletop_party_routes.py`
- New artifact:
  - `modules/<module>/npc_profile_seeds.json`
- Testing:
  - Add phase-specific regression tests for seed contract and runtime alignment.

## Risk and Rollout

- Risk: medium (touches NPC creation callsites and classification filters).
- Mitigation:
  - Additive contract only, lazy materialization preserved.
  - Fail-open where safe, fail-closed on schema-critical corruption.
  - Focused regression + manual smoke for recruit -> promote path.

## Compatibility

- Must preserve SP and TABLETOP MODE behavior.
- Must keep current recruit/promote flows operational during and after migration.
- Must keep host changes merge-safe and clearly marked where required.

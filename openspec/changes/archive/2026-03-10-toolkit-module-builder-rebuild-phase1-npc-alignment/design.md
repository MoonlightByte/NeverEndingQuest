## Context

Module builder currently creates NPC presence at area/location level (`name`, `description`, `attitude`) but does not reliably carry that context into runtime NPC sheet materialization.

Runtime creation paths (`updatePartyNPCs` enlist flow and combat NPC creation fallback) call `npc_builder.py` with sparse arguments. Promotion/readiness logic has already been hardened in web routes, but upstream materialization inputs are still weak.

This phase adds a deterministic bridge from module intent to runtime generation while preserving existing gameplay behavior.

## Goals / Non-Goals

**Goals:**
- Introduce deterministic module-level NPC seed contract.
- Ensure runtime materialization consumes seed context when available.
- Enforce role and profile field consistency in generated NPC sheets.
- Preserve current recruit and NPC -> PC promotion viability.

**Non-Goals:**
- No full toolkit rebuild or UI redesign.
- No async orchestration architecture changes.
- No mandatory eager generation for all module NPC sheets.

## Decisions

1. **Use per-module seed artifact**
   - Decision: write `modules/<module>/npc_profile_seeds.json` from canonicalized module NPC context.
   - Rationale: deterministic runtime input and module-local provenance.
   - Alternative rejected: global shared seed cache (cross-module collision risk).

2. **Keep lazy materialization**
   - Decision: do not generate full NPC character files for all module NPCs during build.
   - Rationale: lower cost, less global `characters/` churn, preserves current flow.
   - Alternative rejected: eager full-sheet generation (higher latency/cost and collision complexity).

3. **Deterministic postprocessing in `npc_builder`**
   - Decision: normalize role fields, seed missing appearance keys, and audit before final write.
   - Rationale: aligns with existing promotion/profile-readiness contracts.
   - Alternative rejected: trust raw LLM output only.

4. **Runtime caller alignment over broad rewrites**
   - Decision: update only key callsites (`action_handler`, `combat_builder`) to pass seed context.
   - Rationale: targeted impact and safer rollout.
   - Alternative rejected: full NPC pipeline rewrite in one phase.

5. **Tightened Add Existing candidate filter**
   - Decision: explicit NPC markers in `type`, `character_type`, or `character_role` must exclude candidate from player list.
   - Rationale: avoid accidental cross-role exposure.

## Data Contract

Seed file contract (initial):
- file: `modules/<module>/npc_profile_seeds.json`
- structure:
  - `module_name`
  - `generated_at`
  - `npcs[]` entries containing:
    - `name`
    - `aliases[]`
    - `source_refs[]` (area/location refs)
    - `description`
    - `attitude`
    - optional hints: `race`, `class`, `background`, `level`
    - optional appearance fields: `age`, `height`, `weight`, `eyes`, `skin`, `hair`

Merge precedence in `npc_builder`:
1) explicit CLI args
2) seed hints
3) builder defaults

## Risks / Trade-offs

- Seed drift from reconciled names -> mitigate by generating seeds after reconciliation and canonical mapping.
- Name collisions in root `characters/` -> reduce by canonical lookup and existing fuzzy name safeguards.
- Provider instability -> keep deterministic fallback fields and robust error handling.
- Behavior regression in enlist/combat -> use targeted regression tests and manual smoke.

## Migration Plan

1. Generate seed artifact in module build pipeline after NPC reconciliation.
2. Extend `npc_builder` interface for optional module seed context.
3. Apply deterministic postprocessing + audit in `npc_builder` output path.
4. Update runtime callsites to pass seed context.
5. Tighten Add Existing candidate filtering rules.
6. Add and run regression tests plus manual recruit -> promote smoke flow.

## Verification Strategy

- Compile checks on touched files.
- Regression tests for:
  - seed artifact generation
  - seed-consumed NPC materialization
  - enlist flow with seed context
  - combat fallback materialization with seed context
  - NPC -> PC promotion compatibility
- Manual smoke:
  - new module generation
  - recruit a module NPC ally
  - promote recruited NPC to PC via Manage Party/Add Existing

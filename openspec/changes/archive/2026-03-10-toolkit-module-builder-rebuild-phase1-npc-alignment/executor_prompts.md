# Executor Prompts - toolkit-module-builder-rebuild-phase1-npc-alignment

---

## Execution Contract

- MUST execute in order: task groups 1 -> 6.
- MUST keep host file edits minimal and mark required hooks with `# TABLETOP MODE:`.
- MUST keep Python-visible text ASCII only.
- MUST preserve current recruit (`updatePartyNPCs`) and NPC -> PC promotion viability.
- MUST preserve lazy NPC materialization behavior (no forced eager generation for all module NPCs).
- SHOULD keep changes additive and extension-first.

---

## Prompt 1 - Seed Contract Generation

Implement tasks 1.1-1.3.

Scope:
- `core/generators/module_builder.py`

Requirements:
- Add module-local NPC seed artifact generation after reconciliation.
- Write `modules/<module>/npc_profile_seeds.json` with canonical NPC identity, aliases, source refs, and optional profile hints.
- Seed generation errors must not fail full module build.

Verify before moving on:
- `python3 -m py_compile core/generators/module_builder.py`
- Manual smoke: generate test module and confirm seed file exists with expected structure.

---

## Prompt 2 - NPC Builder Seed-Aware Materialization

Implement tasks 2.1-2.4.

Scope:
- `core/generators/npc_builder.py`
- (shared helpers only if needed) `utils/character_creation_audit.py`, `utils/pc_manager.py`

Requirements:
- Accept optional module/seed context in NPC builder inputs.
- Merge precedence must be: explicit args > seed hints > defaults.
- Add deterministic postprocessing before final save:
  - role normalization to NPC markers
  - appearance key seeding (`age`, `height`, `weight`, `eyes`, `skin`, `hair`)
  - creation audit validation
- Surface schema-critical failures explicitly.

Verify before moving on:
- `python3 -m py_compile core/generators/npc_builder.py utils/character_creation_audit.py utils/pc_manager.py`

---

## Prompt 3 - Runtime Callsite Alignment

Implement tasks 3.1-3.3.

Scope:
- `core/ai/action_handler.py`
- `core/generators/combat_builder.py`

Requirements:
- Enlist path (`updatePartyNPCs` add flow) passes module seed context into NPC materialization.
- Combat fallback NPC creation path passes module seed context into NPC materialization.
- Preserve current behavior when seed file is missing.

Verify before moving on:
- `python3 -m py_compile core/ai/action_handler.py core/generators/combat_builder.py`
- Manual smoke: recruit ally in module with seed file and without seed file.

---

## Prompt 4 - Add Existing Classification Guard

Implement tasks 4.1-4.2.

Scope:
- `web/routes/tabletop_party_routes.py`

Requirements:
- Exclude explicit NPC-marked files from player candidate listing if any marker field is `npc`:
  - `type`
  - `character_type`
  - `character_role`
- Keep backward compatibility for legacy player files missing role markers.

Verify before moving on:
- `python3 -m py_compile web/routes/tabletop_party_routes.py`
- Manual smoke: Add Existing player list excludes NPC files.

---

## Prompt 5 - Regression Coverage

Implement tasks 5.1-5.4.

Scope:
- Add focused tests for this phase (new script file is acceptable)

Requirements:
- Seed artifact generation/shape tests.
- Seed-aware NPC builder output/postprocessing tests.
- Enlist/combat callsite context wiring tests with fallback behavior.
- NPC -> PC promotion compatibility tests remain passing.

Verify before moving on:
- Run tests added in this phase.

---

## Prompt 6 - Final Verification and Smoke

Implement task group 6.x.

Required final commands:
- `python3 -m py_compile core/generators/module_builder.py core/generators/npc_builder.py core/ai/action_handler.py core/generators/combat_builder.py web/routes/tabletop_party_routes.py`
- `python3 core/validation/validate_module_files.py`
- Run phase-specific regression tests added in Prompt 5.

Manual smoke checklist:
1. Generate a new module and confirm `npc_profile_seeds.json` is created.
2. Recruit a module NPC ally and confirm sheet creation succeeds.
3. Start combat with NPC creation fallback path and confirm no regression.
4. Promote the recruited NPC to PC in Manage Party/Add Existing.
5. Confirm promoted character remains valid and active-character invariants are preserved.

---

## Notes for Implementer

- Keep this phase narrow: data contract and runtime alignment only.
- Do not include unrelated toolkit UI rebuild work in this change.
- Prefer small, testable helpers over broad refactors.

## 1. Contract Locks and Test Scaffolding

- [x] 1.1 Add focused combat contract tests for mixed `updateEncounter` payload preference and explicit routing separation from PC/allied `updateCharacterInfo`.
- [x] 1.2 Add contract coverage for the approved first-wave enemy op family (`hp_delta`, `set_hp`, `condition_add`, `condition_remove`, `set_status`).
- [x] 1.3 Preserve prose-only fallback coverage and fail-open handling for unsupported or ambiguous enemy ops payloads.

## 2. Combat Prompt and Validator Alignment

- [x] 2.1 Update `prompts/combat/combat_sim_prompt_multipc_compressed.txt` to prefer mixed `changes + ops` payloads for enemy-side `updateEncounter` mutations.
- [x] 2.2 Update `prompts/combat/combat_validation_prompt_multipc_compressed.txt` to accept and prefer mixed `changes + ops` payloads for enemy-side `updateEncounter` mutations.
- [x] 2.3 Keep the routing boundary explicit: enemies stay on `updateEncounter`, PCs/allies stay on `updateCharacterInfo`.
- [x] 2.4 Update mirror combat prompt files only as needed for parity/docs.

## 3. Narrow Runtime Alignment

- [x] 3.1 Inspect `core/ai/action_handler.py` and `updates/update_encounter.py` for any encounter-ops routing gap exposed by the new tests.
- [x] 3.2 If needed, apply only narrow deterministic handling for the approved first-wave enemy ops while preserving prose fallback behavior.
- [x] 3.3 Avoid widening runtime scope to spawn/despawn, initiative reorder, topology ops, or roll-resolution behavior.

## 4. Verification

- [x] 4.1 Run targeted contract tests for the new combat encounter-ops slice.
- [x] 4.2 Keep `scripts/test_combat_structured_ops_contract.py`, `scripts/test_multi_pc_combat.py`, and `scripts/c5_regression_combat.py` green.
- [x] 4.3 Run `python3 -m py_compile` for any touched Python files.
- [x] 4.4 Run `openspec validate combat-encounter-ops-second-wave`.

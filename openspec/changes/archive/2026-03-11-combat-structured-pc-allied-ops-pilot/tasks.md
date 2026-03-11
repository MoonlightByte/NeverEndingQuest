## 1. Contract Locks and Test Scaffolding

- [x] 1.1 Add focused combat contract tests for mixed `updateCharacterInfo` payload preference and explicit enemy-side `updateEncounter` deferral.
- [x] 1.2 Add contract coverage for supported combat-facing ops examples (`hp_delta`, `set_hp`, `spell_slot_delta`, `condition_add`, `condition_remove`, `inventory_remove`, `inventory_add`).
- [x] 1.3 Preserve prose-only fallback coverage and mixed-payload acceptance in combat-specific tests.

## 2. Combat Prompt and Validator Alignment

- [x] 2.1 Update `prompts/combat/combat_sim_prompt_multipc_compressed.txt` to prefer mixed `changes + ops` payloads for PC/allied updates.
- [x] 2.2 Update `prompts/combat/combat_validation_prompt_multipc_compressed.txt` to accept and prefer mixed `changes + ops` payloads for PC/allied updates.
- [x] 2.3 Keep enemy-side `updateEncounter` guidance unchanged and explicit in both combat prompt and validator.
- [x] 2.4 Update mirror combat prompt files only as needed for parity/docs.

## 3. Narrow Runtime Alignment

- [x] 3.1 Inspect `core/ai/action_handler.py` and `updates/update_character_info.py` for any combat-specific routing gap exposed by the new tests.
- [x] 3.2 If needed, apply only narrow runtime adjustments that preserve existing structured-ops markers and prose fallback behavior.
- [x] 3.3 Avoid widening runtime scope to `updateEncounter.ops` or save/check handling.

## 4. Verification

- [x] 4.1 Run targeted contract tests for the new combat structured-ops slice.
- [x] 4.2 Keep `scripts/test_update_character_ops_contract.py`, `scripts/test_multi_pc_combat.py`, and `scripts/c5_regression_combat.py` green.
- [x] 4.3 Run `python3 -m py_compile` for any touched Python files.
- [x] 4.4 Run `openspec validate combat-structured-pc-allied-ops-pilot`.

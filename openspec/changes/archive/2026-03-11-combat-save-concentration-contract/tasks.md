## 1. Contract Locks and Test Scaffolding

- [x] 1.1 Add focused combat contract tests for `requestRoll` preference, stop-after-request semantics, and explicit prose-compatibility fallback.
- [x] 1.2 Add combat-specific concentration contract coverage for `max(10, floor(damage / 2))` and no same-response contingent outcome narration.

## 2. Combat Prompt and Validator Alignment

- [x] 2.1 Update `prompts/combat/combat_sim_prompt_multipc_compressed.txt` to prefer `requestRoll` for saves/checks/concentration pauses.
- [x] 2.2 Update `prompts/combat/combat_validation_prompt_multipc_compressed.txt` to accept and prefer `requestRoll` for saves/checks/concentration pauses.
- [x] 2.3 Keep prose-only save/check requests documented as compatibility-valid during migration.
- [x] 2.4 Update mirror combat prompt files only as needed for parity/docs.

## 3. Narrow Runtime Alignment

- [x] 3.1 Inspect `core/managers/combat_manager.py` and `core/ai/action_handler.py` for any combat-specific gap exposed by the new tests.
- [x] 3.2 If needed, apply only minimal runtime alignment that preserves current pause semantics and avoids roll-resolution scope.
- [x] 3.3 Avoid widening runtime scope into enemy ops or full save/check resolution.

## 4. Verification

- [x] 4.1 Run targeted combat contract tests for the new save/concentration slice.
- [x] 4.2 Keep `scripts/test_save_concentration_contract.py`, `scripts/test_multi_pc_combat.py`, and `scripts/c5_regression_combat.py` green.
- [x] 4.3 Run `python3 -m py_compile` for any touched Python files.
- [x] 4.4 Run `openspec validate combat-save-concentration-contract`.

## 1. Prompt Authority and Contract Locks

- [x] 1.1 Add source-contract tests proving live multi-PC combat sim and validation load the compressed prompt files.
- [x] 1.2 Update `core/managers/combat_manager.py` prompt loader paths so compressed multi-PC combat prompts are the canonical runtime authority.
- [x] 1.3 Preserve single-player compatibility and existing TT phase-sync behavior while switching prompt authority.

## 2. Combat Context Packet Reduction

- [x] 2.1 Add combat payload hygiene tests for duplicated-state reduction and required phase/actor packet preservation.
- [x] 2.2 Trim duplicated or overlapping runtime prompt sections in `core/managers/combat_manager.py` and `core/managers/multi_pc_combat.py` while preserving legal actor, round, and stop-boundary fidelity.
- [x] 2.3 Reorder and slim `prompts/combat/combat_sim_prompt_multipc_compressed.txt` and `prompts/combat/combat_validation_prompt_multipc_compressed.txt` so hard constraints and authority rules precede flavor guidance.

## 3. Combat Validation Efficiency and Truth Packs

- [x] 3.1 Add targeted tests for combat validation telemetry fields, reason codes, and threshold-based compression routing.
- [x] 3.2 Add combat validation helper wiring for deterministic payload-size telemetry and threshold-based compression decisions.
- [x] 3.3 Add compact touched-combatant truth-pack helpers for PC/allied `updateCharacterInfo` mutations and integrate them into combat validation context.
- [x] 3.4 Preserve fail-open helper fallback if truth-pack assembly or compression fails.

## 4. Combat Retry Hygiene

- [x] 4.1 Add regression tests proving combat validation correction notes and invalid-JSON retry notes do not persist as combat conversation-history user turns.
- [x] 4.2 Refactor combat validation retry flow so correction notes remain validation-local while still reaching the retry attempt.

## 5. Verification

- [x] 5.1 Run targeted tests for prompt authority, payload hygiene, validation telemetry/compression, truth-pack behavior, and retry hygiene.
- [x] 5.2 Run `python3 -m py_compile` for touched Python files and keep `scripts/test_multi_pc_combat.py` and `scripts/c5_regression_combat.py` green.
- [x] 5.3 Run `openspec validate combat-runtime-authority-and-efficiency`.

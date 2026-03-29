## 1. Contract Locks and Regression Scaffolding

- [ ] 1.1 Add targeted combat regression coverage for explicit miss->hit narration contradictions in enemy phase.
- [ ] 1.2 Add targeted combat regression coverage for explicit hit->miss narration contradictions in enemy phase.
- [ ] 1.3 Add regression coverage for `updateEncounter` prose or ops that incorrectly target a PC or allied NPC.
- [ ] 1.4 Add fail-open regression coverage for ambiguous narration that should not be rejected deterministically.

## 2. Deterministic Guard Implementation

- [ ] 2.1 Add a narrow helper under `utils/` to evaluate hit/miss narration consistency from explicit attack math and AC context.
- [ ] 2.2 Add a narrow helper or bounded guard path to reject `updateEncounter` payloads that mutate PC/allied state.
- [ ] 2.3 Wire the new deterministic guards into `core/managers/combat_manager.py` before probabilistic combat validation.
- [ ] 2.4 Keep the new guards fail-open for ambiguous prose or non-authoritative math.

## 3. Validator Parity

- [ ] 3.1 Update `prompts/combat/combat_validation_prompt_multipc_compressed.txt` with explicit miss->hit and hit->miss contradiction guidance.
- [ ] 3.2 Update `prompts/combat/combat_validation_prompt_multipc.txt` with matching narrow parity guidance.
- [ ] 3.3 Avoid broad combat prompt rewrites outside contradiction handling and routing-boundary clarity.

## 4. Verification

- [ ] 4.1 Run targeted regression tests for combat narration consistency and routing-boundary rejection.
- [ ] 4.2 Keep `scripts/test_multi_pc_combat.py` and `scripts/c5_regression_combat.py` green.
- [ ] 4.3 Run `python3 -m py_compile` on all touched Python files.
- [ ] 4.4 Run `openspec validate tt-combat-hit-miss-narration-sync`.

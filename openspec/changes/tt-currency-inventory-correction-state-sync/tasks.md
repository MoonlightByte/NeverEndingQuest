## 1. Runtime Guardrails

- [x] 1.1 Add a narrow explicit bookkeeping-correction detector in `utils/deterministic_mechanics_precheck.py` that fails closed when committed currency/inventory correction claims lack matching `updateCharacterInfo` coverage.
- [x] 1.2 Wire the bookkeeping-correction guard through `main.py` before low-risk skip routing so `narration_only` cannot finalize those turns early.
- [x] 1.3 Tighten `utils/validation_routing.py` so explicit bookkeeping-correction turns are ineligible for `narration_only` skip until matching state-mutation actions are present.

## 2. Prompt And Validator Contract Parity

- [x] 2.1 Update `prompts/system_prompt_compressed.txt` to distinguish ruling-only clarification from committed bookkeeping correction and replace misleading coin-as-inventory examples with currency-aware examples.
- [x] 2.2 Update `prompts/validation/validation_prompt_compressed.txt` with an explicit invalid case for narration-only bookkeeping correction and clear retry guidance to emit missing `updateCharacterInfo` coverage.
- [x] 2.3 Mirror any required contract wording in uncompressed prompt/validator surfaces only where existing parity expectations require it.

## 3. Regression Coverage

- [x] 3.1 Extend `scripts/test_validation_skip_routing.py` with cases proving bookkeeping-correction turns cannot use `narration_only` skip while pure clarification still can.
- [x] 3.2 Add or extend deterministic-mechanics tests to cover coin-pouch correction, payment/refund, and narrated gain/loss cases with and without matching `updateCharacterInfo` actions.
- [x] 3.3 Add prompt source-contract checks to lock the new clarification-vs-correction wording and currency-aware examples.

## 4. Verification

- [x] 4.1 Run `python3 -m py_compile main.py utils/validation_routing.py utils/deterministic_mechanics_precheck.py` and fix any syntax issues.
- [x] 4.2 Run targeted regression suites for validation skip routing and deterministic mechanics, plus any new prompt source-contract tests added by this change.
- [x] 4.3 Review the affected runtime path to confirm single-player and tabletop behavior remain backward compatible and fail closed only for explicit bookkeeping-correction drift.

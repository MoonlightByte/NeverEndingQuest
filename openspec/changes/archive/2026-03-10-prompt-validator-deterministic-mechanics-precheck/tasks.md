## 1. Deterministic Precheck Utility

- [x] 1.1 Add utility module for deterministic mechanics precheck focused on `updateCharacterInfo` actions.
- [x] 1.2 Implement explicit HP contradiction checks (`0 <= target_hp <= maxHitPoints`) for parseable HP transitions.
- [x] 1.3 Implement explicit spell-slot ratio contradiction checks for parseable `current/max` slot values.
- [x] 1.4 Implement explicit item-removal quantity checks against tracked inventory/ammunition when parseable and matched.

## 2. Validation Pipeline Integration

- [x] 2.1 Integrate deterministic mechanics precheck into `validate_ai_response()` before LLM validation call.
- [x] 2.2 Ensure deterministic failures return clear reason text and block validation flow.
- [x] 2.3 Ensure ambiguous/unparseable updates remain fail-open.

## 3. Regression Coverage

- [x] 3.1 Add targeted tests for helper pass/fail behavior across HP, slots, and inventory-removal checks.
- [x] 3.2 Add source-contract test ensuring precheck is invoked in validation pipeline.

## 4. Verification

- [x] 4.1 Run targeted tests for deterministic precheck and related prompt-validator contract suites.
- [x] 4.2 Run syntax checks and `openspec validate` for this change.

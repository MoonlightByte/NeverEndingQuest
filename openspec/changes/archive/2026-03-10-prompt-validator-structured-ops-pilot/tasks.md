## 1. Contract and Tests

- [x] 1.1 Add targeted contract tests for `updateCharacterInfo.parameters.ops` support in prompt, validator, and runtime references.
- [x] 1.2 Add tests that lock the initial supported ops set.
- [x] 1.3 Add tests that preserve legacy `changes`-only compatibility and mixed `changes`+`ops` payload acceptance.

## 2. Prompt and Validator Contract Update

- [x] 2.1 Update compressed narrator prompt to document additive `ops` support.
- [x] 2.2 Update compressed validator prompt to accept additive `ops` support.
- [x] 2.3 Keep legacy prose `changes` path documented as fallback.

## 3. Deterministic Runtime Application

- [x] 3.1 Add helper(s) to validate supported ops.
- [x] 3.2 Add deterministic application for HP, slots, inventory, currency, and condition ops.
- [x] 3.3 Keep unsupported/absent ops on conservative fallback behavior.

## 4. Fallback Telemetry and Mixed-Mode Verification

- [x] 4.1 Emit deterministic fallback usage markers when prose path is used.
- [x] 4.2 Add runtime tests for structured-only, prose-only, and mixed payloads.

## 5. Verification

- [x] 5.1 Run targeted ops contract and runtime application tests.
- [x] 5.2 Run syntax checks and `openspec validate` for this change.

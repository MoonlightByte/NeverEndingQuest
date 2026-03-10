## 1. Contract and Tests

- [x] 1.1 Add focused contract tests for `requestRoll` prompt, validator, and runtime reference expectations.
- [x] 1.2 Add tests that lock the `requestRoll.parameters` payload shape and allowed `rollType` values.
- [x] 1.3 Add tests that lock the concentration DC rule as `max(10, floor(damage / 2))`.
- [x] 1.4 Add tests that preserve prose-only save/check narration as a compatibility path.

## 2. Prompt and Validator Contract Update

- [x] 2.1 Update the compressed narrator prompt to document `requestRoll` as a lightweight first-class save/check contract.
- [x] 2.2 Update the compressed validator prompt to accept `requestRoll` and require pause-after-request behavior.
- [x] 2.3 Keep prose-only save/check guidance documented as compatibility fallback during migration.
- [x] 2.4 Align prompt wording for the deterministic concentration DC rule.

## 3. Runtime Scaffolding

- [x] 3.1 Add a small helper or validation path for `requestRoll.parameters`.
- [x] 3.2 Add a deterministic concentration DC helper using `max(10, floor(damage / 2))`.
- [x] 3.3 Add minimal runtime references in the expected parser/consumer files without building full roll resolution.

## 4. Compatibility and Negative-Path Verification

- [x] 4.1 Add runtime-facing tests for structured `requestRoll`, prose-only requests, and concentration-linked request metadata.
- [x] 4.2 Add negative tests for invalid `requestRoll` payloads and malformed concentration inputs.
- [x] 4.3 Verify current save/check pause semantics remain intact for both SP and TT paths.

## 5. Verification

- [x] 5.1 Run targeted contract tests for the new save/check and concentration contract.
- [x] 5.2 Run syntax checks for any touched Python files.
- [x] 5.3 Run `openspec validate prompt-validator-save-concentration-contract`.

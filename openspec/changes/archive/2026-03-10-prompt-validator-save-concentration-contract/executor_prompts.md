## Builder Execution Prompts - prompt-validator-save-concentration-contract

Use this guide with `tasks.md`. Execute in order and verify after each prompt.

---

## Prompt 1 - Contract and Tests

Implement tasks 1.1 through 1.4 only.

Goal:
- Lock the first-class save/check contract and concentration DC rule before changing prompts or runtime behavior.

Allowed:
- `scripts/test_save_concentration_contract.py`
- any new tiny helper fixture inside the test file only if needed

Forbidden:
- no prompt edits yet
- no runtime behavior edits yet
- no combat loop rewrites
- no dice-engine work

Required:
- Add focused tests that lock `requestRoll` as the default action name for the new contract.
- Lock this minimum payload shape in tests:
  - `characterName`
  - `rollType`
  - `dc`
  - `reason`
  - conditional `ability` / `skill`
  - optional `advantage`
- Lock allowed `rollType` values to `saving_throw`, `ability_check`, and `skill_check`.
- Add tests that preserve backward compatibility for prose-only save/check narration.
- Add tests that lock the concentration DC rule as `max(10, floor(damage / 2))`.
- Add source-reference tests for the expected future touchpoints:
  - `main.py`
  - `core/managers/combat_manager.py`
  - `core/ai/action_handler.py`
  - compressed narrator/validator prompts

Constraints:
- MUST keep the slice test-only.
- MUST use ASCII only.
- MUST keep test assertions explicit and source-contract oriented.
- SHOULD model the new tests after the existing prompt-validator contract suites.

Verify:
```bash
python3 -m py_compile scripts/test_save_concentration_contract.py
python3 scripts/test_save_concentration_contract.py
```

Report:
- exact payload fields locked by tests
- exact `rollType` values locked by tests
- exact concentration formula locked by tests
- exact files expected for Prompt 2 runtime/prompt work

---

## Prompt 2 - Prompt and Validator Contract Update

Implement tasks 2.1 through 2.4 only.

Goal:
- Document the new save/check contract in the canonical compressed prompts while preserving current prose compatibility.

Allowed:
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `scripts/test_save_concentration_contract.py` only if test expectations need additive updates

Forbidden:
- no runtime parsing yet
- no combat prompt overhaul
- no uncompressed prompt rewrites unless a tiny reference note is strictly required after the compressed update is complete

Required:
- Add `requestRoll` to the compressed narrator action contract as a lightweight first-class save/check request.
- Document the minimum payload shape consistently with the tests.
- State that the narrator MUST stop after issuing `requestRoll` and wait for the player roll.
- Update the compressed validator prompt so `requestRoll` is accepted and pause semantics are enforced.
- Align concentration wording with the deterministic formula `max(10, floor(damage / 2))`.
- Keep prose-only save/check requests documented as compatibility fallback during migration.

Constraints:
- MUST treat compressed prompts as canonical runtime source.
- MUST keep wording concise and machine-checkable.
- SHOULD reduce ambiguity rather than add lore/examples.

Verify:
```bash
python3 scripts/test_save_concentration_contract.py
```

Report:
- exact prompt sections updated
- exact wording used for pause semantics
- whether any additional prompt files appear necessary for a later follow-up

---

## Prompt 3 - Runtime Scaffolding

Implement tasks 3.1 through 3.3 only.

Goal:
- Add the smallest runtime scaffolding needed to recognize the new contract and centralize concentration DC calculation, without building result resolution.

Allowed:
- `core/ai/action_handler.py`
- `main.py`
- `core/managers/combat_manager.py`
- one new helper under `utils/` or `core/validation/`
- `scripts/test_save_concentration_contract.py`

Forbidden:
- no full dice engine
- no broad control-flow rewrites in combat loops
- no changes outside the listed files

Required:
- Add a small helper to validate or normalize `requestRoll.parameters`.
- Add a deterministic concentration DC helper implementing `max(10, floor(damage / 2))`.
- Add minimal source-level runtime references so the new contract has a defined parser/consumer boundary.
- Preserve current gameplay behavior; this phase is scaffolding, not full adoption.

Edit Strategy:
- Apply one anchored patch at a time, then re-run `py_compile` before the next patch.

Constraints:
- MUST keep changes additive and merge-safe.
- MUST mark required host-file edits with `# TABLETOP MODE:` comments.
- MUST preserve prose-only compatibility.
- SHOULD prefer helper extraction over deep inline edits.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py main.py core/managers/combat_manager.py
python3 scripts/test_save_concentration_contract.py
```

Report:
- exact helper name(s) added
- exact runtime files now referencing `requestRoll`
- whether runtime behavior changed or remained scaffold-only

---

## Prompt 4 - Compatibility and Negative-Path Verification

Implement tasks 4.1 through 4.3 only.

Goal:
- Prove the new contract is compatible with current prose behavior and rejects malformed structured requests safely.

Allowed:
- `scripts/test_save_concentration_contract.py`
- any tiny helper test support needed in the same file
- minimal runtime touch-up only if a failing negative-path contract requires a surgical fix in files already touched in Prompt 3

Forbidden:
- no new feature expansion
- no combat prompt rewrites
- no unrelated validation cleanup

Required:
- Add tests for:
  - valid structured `requestRoll`
  - prose-only save/check compatibility
  - concentration-linked request metadata or helper usage
  - invalid payload rejection (missing `characterName`, missing `dc`, bad `rollType`, missing `ability`/`skill` where required)
  - malformed concentration inputs
- Verify pause semantics are preserved for both SP and TT expectations.

Constraints:
- MUST fail closed for malformed structured payloads.
- MUST keep prose compatibility passing.
- SHOULD keep the test matrix narrow and explicit.

Verify:
```bash
python3 -m py_compile scripts/test_save_concentration_contract.py
python3 scripts/test_save_concentration_contract.py
```

Report:
- negative cases added
- compatibility cases added
- any runtime fix required to satisfy the negative-path contracts

---

## Prompt 5 - Final Verification

Implement tasks 5.1 through 5.3.

Goal:
- Finish the slice, confirm the change is internally coherent, and make it ready for apply/verify review.

Required:
- Run the targeted test suite.
- Run syntax checks for all touched Python files.
- Run `openspec validate prompt-validator-save-concentration-contract`.
- Update `tasks.md` to mark completed items.
- Do not archive the change in this prompt unless explicitly instructed later.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py main.py core/managers/combat_manager.py scripts/test_save_concentration_contract.py
python3 scripts/test_save_concentration_contract.py
openspec validate prompt-validator-save-concentration-contract
```

Ready signal:
- `prompt-validator-save-concentration-contract is apply-ready.`

Report:
- PASS/FAIL for each verification command
- exact files changed across the full 5-prompt sequence
- any deferred follow-up discovered during implementation

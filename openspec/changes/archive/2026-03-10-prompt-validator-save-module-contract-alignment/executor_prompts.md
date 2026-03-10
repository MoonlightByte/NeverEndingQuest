## Builder Execution Prompts - prompt-validator-save-module-contract-alignment

Use this guide with `tasks.md`. Execute in order and stop after each prompt for verification.

---

## Execution Contract

MUST:
- MUST implement only the covered action set:
  - `saveGame`
  - `restoreGame`
  - `listSaves`
  - `deleteSave`
  - `createNewModule`
- MUST keep runtime as the baseline unless an obvious bug is found.
- MUST keep edits limited to prompt/validator files, covered runtime touchpoints, and focused regression tests.
- MUST preserve the existing player-commitment gate for `createNewModule`.
- MUST keep Python log/output text ASCII-only.
- MUST avoid save-system or module-builder rewrites in this change.

SHOULD:
- SHOULD prefer additive tests and small prompt edits.
- SHOULD add concise `# TABLETOP MODE:` markers only if a host-file runtime shim is needed.
- SHOULD record out-of-scope drift for later work rather than fixing it here.

Edit Strategy:
- Add parity tests first.
- Align compressed prompt files next.
- Mirror changes into uncompressed prompt files.
- Touch runtime only if tests prove a covered compatibility shim is needed.

---

## Prompt 1 - Audit Covered Runtime Contracts + Add Parity Tests

Implement tasks 1.1 through 1.3 and task 3.1.

Goal:
- Lock the canonical Phase 1B contract in tests before editing prompts.

Scope:
- `core/ai/action_handler.py` (read/audit; edit only if tiny normalization is clearly needed)
- `core/generators/module_builder.py` (read/audit)
- new focused regression test file(s), for example:
  - `scripts/test_prompt_validator_save_module_contracts.py`

Required:
- Add source-level regression coverage that asserts runtime baseline for:
  - `saveGame` -> `description` and `saveMode`
  - `restoreGame` -> `saveFolder`
  - `listSaves` -> `{}`
  - `deleteSave` -> `saveFolder`
  - `createNewModule` -> narrative-driven payload accepted by runtime
- Add tests that fail if prompt/validator files still require stale `saveName` for `restoreGame` or `deleteSave`.
- Add tests that fail if validator guidance still treats `moduleName` plus `startingLocation` as the only valid `createNewModule` contract.
- Keep tests ASCII-only and deterministic.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py core/generators/module_builder.py
python3 scripts/test_prompt_validator_save_module_contracts.py
```

Report:
- List the exact canonical parameter shapes locked by tests.
- Note any out-of-scope drift discovered during the audit.

---

## Prompt 2 - Align Compressed Prompt Contracts

Implement tasks 2.1 and 2.2.

Scope:
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`

Required:
- Update covered save-management action guidance to match runtime parameter shapes.
- Remove stale `saveName` requirements for covered actions.
- Add or update `createNewModule` parameter guidance so `narrative` is the canonical minimum payload.
- Preserve the existing commitment gate for `createNewModule`.

Verify:
```bash
python3 scripts/test_prompt_validator_save_module_contracts.py
```

Report:
- Summarize each compressed prompt contract change in one line.

---

## Prompt 3 - Mirror Uncompressed Prompt Contracts + Minimal Runtime Shim if Needed

Implement task 2.3 and task 3.2 if required.

Scope:
- `prompts/system_prompt.txt`
- `prompts/validation/validation_prompt.txt`
- `core/ai/action_handler.py` only if a tiny compatibility shim is justified by failing tests

Required:
- Mirror the covered contract alignment into uncompressed prompt files.
- Keep wording consistent with compressed variants.
- If and only if tests reveal a live legacy dependency, add the smallest covered runtime normalization needed.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py
python3 scripts/test_prompt_validator_save_module_contracts.py
```

Report:
- State whether a runtime shim was needed; if yes, describe it in one sentence.

---

## Prompt 4 - Final Verification and Handoff

Implement tasks 3.3, 4.1, and 4.2.

Required:
- Record newly confirmed out-of-scope drift for later work.
- Run focused verification and update `tasks.md` accordingly.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py core/generators/module_builder.py
python3 scripts/test_prompt_validator_save_module_contracts.py
openspec validate prompt-validator-save-module-contract-alignment
```

Report:
- PASS/FAIL for each command
- changed file list
- short risk note

Ready signal:
- "prompt-validator-save-module-contract-alignment is apply-ready."

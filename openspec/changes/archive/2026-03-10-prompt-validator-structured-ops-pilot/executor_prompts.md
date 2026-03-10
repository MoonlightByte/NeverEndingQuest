## Builder Execution Prompts - prompt-validator-structured-ops-pilot

Use this guide with `tasks.md`. Execute in order and verify after each prompt.

---

## Prompt 1 - Contract and Tests

Implement tasks 1.1 through 1.3 only.

Goal:
- Lock the additive `ops` contract before changing runtime behavior.

Scope:
- new focused tests, for example:
  - `scripts/test_update_character_ops_contract.py`

Required:
- Add contract tests for `updateCharacterInfo.parameters.ops` in prompt, validator, and runtime references.
- Add tests that lock the initial supported ops set.
- Add tests that preserve legacy `changes`-only compatibility and mixed `changes`+`ops` acceptance.
- Do not implement runtime application yet.

Verify:
```bash
python3 -m py_compile scripts/test_update_character_ops_contract.py
python3 scripts/test_update_character_ops_contract.py
```

Report:
- exact ops types locked by tests
- exact files that will need edits in the next slice
- PASS/FAIL for verification commands

---

## Prompt 2 - Prompt and Validator Contract Update

Implement tasks 2.1 through 2.3 only.

Scope:
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`

Required:
- Document additive `ops` support.
- Keep legacy prose fallback documented.
- Do not change runtime application yet.

Verify:
```bash
python3 scripts/test_update_character_ops_contract.py
```

---

## Prompt 3 - Deterministic Runtime Application

Implement tasks 3.1 through 3.3 only.

Scope:
- `core/ai/action_handler.py`
- `updates/update_character_info.py`
- new helper under `utils/` or `core/validation/`

Required:
- Validate and apply the supported ops set directly in Python.
- Preserve conservative fallback behavior.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py updates/update_character_info.py
python3 scripts/test_update_character_ops_contract.py
```

---

## Prompt 4 - Fallback Telemetry and Mixed-Mode Verification

Implement tasks 4.1 and 4.2 only.

Required:
- Emit deterministic fallback markers for prose path.
- Add structured-only, prose-only, and mixed payload tests.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py updates/update_character_info.py scripts/test_update_character_ops_contract.py
python3 scripts/test_update_character_ops_contract.py
```

---

## Prompt 5 - Final Verification

Implement tasks 5.1 and 5.2.

Verify:
```bash
python3 -m py_compile core/ai/action_handler.py updates/update_character_info.py scripts/test_update_character_ops_contract.py
python3 scripts/test_update_character_ops_contract.py
openspec validate prompt-validator-structured-ops-pilot
```

Ready signal:
- "prompt-validator-structured-ops-pilot is apply-ready."

## Builder Execution Prompts - prompt-validator-deterministic-mechanics-precheck

Use this guide with `tasks.md`. Execute in order and verify after each prompt.

---

## Prompt 1 - Tests First for Covered Contradictions

Implement tasks 3.1 and 3.2 first.

Goal:
- Lock expected behavior before runtime wiring.

Scope:
- New test file (for example `scripts/test_deterministic_mechanics_precheck.py`)
- Source-contract assertion in tests for `validate_ai_response()` call-site integration

Required:
- Add tests for HP overflow/negative fail, slot ratio fail, inventory over-removal fail, and fail-open unparseable text.
- Add source-contract test that precheck invocation exists in `main.py`.

Verify:
```bash
python3 -m py_compile scripts/test_deterministic_mechanics_precheck.py
python3 scripts/test_deterministic_mechanics_precheck.py
```

---

## Prompt 2 - Implement Utility Module

Implement tasks 1.1 through 1.4.

Scope:
- New utility module under `utils/`.

Required:
- Add bounded parser helpers for covered explicit patterns.
- Keep parsing conservative and fail-open when uncertain.
- Return deterministic failure reason on covered contradictions.

Verify:
```bash
python3 -m py_compile utils/deterministic_mechanics_precheck.py scripts/test_deterministic_mechanics_precheck.py
python3 scripts/test_deterministic_mechanics_precheck.py
```

---

## Prompt 3 - Wire Validation Pipeline

Implement tasks 2.1 through 2.3.

Scope:
- `main.py`

Required:
- Invoke deterministic precheck before LLM validator API call.
- Return immediate validation failure with deterministic reason when precheck fails.
- Preserve fail-open behavior for unparseable text.

Verify:
```bash
python3 -m py_compile main.py utils/deterministic_mechanics_precheck.py
python3 scripts/test_deterministic_mechanics_precheck.py
```

---

## Prompt 4 - Final Verification and Archive Readiness

Implement task 4.1 and 4.2.

Required:
- Run targeted suites including existing contract tests.
- Mark tasks complete.
- Validate change scaffold.

Verify:
```bash
python3 -m py_compile main.py utils/deterministic_mechanics_precheck.py scripts/test_deterministic_mechanics_precheck.py scripts/test_prompt_validator_rest_contract.py scripts/test_prompt_validator_save_module_contracts.py
python3 scripts/test_deterministic_mechanics_precheck.py
python3 scripts/test_prompt_validator_rest_contract.py
python3 scripts/test_prompt_validator_save_module_contracts.py
openspec validate prompt-validator-deterministic-mechanics-precheck
```

Ready signal:
- "prompt-validator-deterministic-mechanics-precheck is apply-ready."

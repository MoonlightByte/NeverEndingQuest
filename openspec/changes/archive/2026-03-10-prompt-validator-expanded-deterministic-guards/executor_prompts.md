## Builder Execution Prompts - prompt-validator-expanded-deterministic-guards

Use this guide with `tasks.md`. Execute in order and verify after each prompt.

---

## Prompt 1 - Contract and Tests

Implement tasks 1.1 through 1.5 only.

Goal:
- Lock the expanded deterministic guard domains before changing helper/runtime behavior.

Allowed:
- `scripts/test_expanded_deterministic_guards_contract.py`
- additive read-only inspection of current deterministic-precheck sources for test expectations

Forbidden:
- no runtime helper edits yet
- no prompt edits yet
- no combat-flow changes
- no broad validator-routing changes

Required:
- Add focused tests that lock the following guard domains:
  1. cantrip/no-slot legality
  2. explicit slot-underflow contradictions
  3. explicit unconscious-vs-HP contradictions
  4. explicit ammo legality beyond only "Removed N arrows" phrasing
  5. explicit short-rest and long-rest duration minimums
- Add tests that preserve fail-open behavior for ambiguous or unparseable text.
- Add source-contract expectations for likely implementation touchpoints:
  - `utils/deterministic_mechanics_precheck.py`
  - `scripts/test_deterministic_mechanics_precheck.py`
  - `main.py`
  - compressed prompt/validator files only as future touchpoints, not mandatory edit targets in this prompt

Constraints:
- MUST keep the slice test-only.
- MUST use ASCII only.
- MUST keep assertions explicit and deterministic.
- SHOULD mirror the style of existing prompt-validator contract suites.

Verify:
```bash
python3 -m py_compile scripts/test_expanded_deterministic_guards_contract.py
python3 scripts/test_expanded_deterministic_guards_contract.py
```

Report:
- exact guard domains locked by tests
- exact files expected for Prompt 2 helper work
- explicit fail-open cases preserved by tests

---

## Prompt 2 - Helper Expansion

Implement tasks 2.1 through 2.4 only.

Goal:
- Extend the deterministic precheck helpers for the new contradiction classes while keeping parsing bounded and fail-open.

Allowed:
- `utils/deterministic_mechanics_precheck.py`
- `scripts/test_expanded_deterministic_guards_contract.py`
- `scripts/test_deterministic_mechanics_precheck.py`

Forbidden:
- no prompt edits unless strictly required by a failing contract test
- no `main.py` pipeline rewrites yet
- no combat/system architecture changes

Required:
- Add helper coverage for:
  - explicit cantrip/no-slot contradictions
  - explicit slot-underflow contradictions against known slot state
  - explicit unconscious-with-above-zero-HP contradictions
  - explicit ammo spend/use/fire contradictions against known tracked ammo
  - explicit parseable rest-duration contradictions
- Keep all ambiguous or unmatched cases fail-open.

Edit Strategy:
- Apply one anchored patch at a time, then re-run `py_compile` before the next patch.

Verify:
```bash
python3 -m py_compile utils/deterministic_mechanics_precheck.py scripts/test_expanded_deterministic_guards_contract.py scripts/test_deterministic_mechanics_precheck.py
python3 scripts/test_expanded_deterministic_guards_contract.py
python3 scripts/test_deterministic_mechanics_precheck.py
```

---

## Prompt 3 - Pipeline Wiring and Narrow Contract Parity

Implement tasks 3.1 through 3.3 only.

Goal:
- Ensure the expanded helpers are used through the existing deterministic precheck path, with only narrow contract-parity edits if implementation proves they are needed.

Allowed:
- `main.py`
- `utils/deterministic_mechanics_precheck.py`
- `scripts/test_expanded_deterministic_guards_contract.py`
- `scripts/test_deterministic_mechanics_precheck.py`
- `prompts/system_prompt_compressed.txt` only if required
- `prompts/validation/validation_prompt_compressed.txt` only if required

Forbidden:
- no broad prompt reorder
- no validator routing redesign
- no combat-flow changes

Required:
- Verify or add the existing callsite integration in `validate_ai_response()`.
- Add source-contract checks for the call path if needed.
- Update compressed prompt/validator wording only if failing tests show the new deterministic guard domains would drift from the runtime contract.

Verify:
```bash
python3 -m py_compile main.py utils/deterministic_mechanics_precheck.py scripts/test_expanded_deterministic_guards_contract.py scripts/test_deterministic_mechanics_precheck.py
python3 scripts/test_expanded_deterministic_guards_contract.py
python3 scripts/test_deterministic_mechanics_precheck.py
```

---

## Prompt 4 - Negative-Path and Fail-Open Verification

Implement tasks 4.1 through 4.3 only.

Goal:
- Prove the new guard set rejects explicit contradictions while still failing open on ambiguity.

Allowed:
- `scripts/test_expanded_deterministic_guards_contract.py`
- `scripts/test_deterministic_mechanics_precheck.py`
- minimal surgical helper/runtime touch-up only if a failing contract requires it

Forbidden:
- no new feature expansion
- no prompt bulk edits
- no unrelated cleanup

Required:
- Add ambiguous-text pass cases for every new guard domain.
- Add deterministic negative tests for every explicit contradiction class.
- Confirm no scope creep into combat flow or broad prose interpretation.

Verify:
```bash
python3 -m py_compile scripts/test_expanded_deterministic_guards_contract.py scripts/test_deterministic_mechanics_precheck.py
python3 scripts/test_expanded_deterministic_guards_contract.py
python3 scripts/test_deterministic_mechanics_precheck.py
```

---

## Prompt 5 - Final Verification

Implement tasks 5.1 through 5.3.

Goal:
- Finish the slice cleanly and make the change apply-ready.

Required:
- Run the targeted deterministic-guard suites.
- Run syntax checks for all touched Python files.
- Update `tasks.md` to mark completed items.
- Run `openspec validate prompt-validator-expanded-deterministic-guards`.
- Do not archive in this prompt unless explicitly instructed later.

Verify:
```bash
python3 -m py_compile main.py utils/deterministic_mechanics_precheck.py scripts/test_expanded_deterministic_guards_contract.py scripts/test_deterministic_mechanics_precheck.py
python3 scripts/test_expanded_deterministic_guards_contract.py
python3 scripts/test_deterministic_mechanics_precheck.py
openspec validate prompt-validator-expanded-deterministic-guards
```

Ready signal:
- `prompt-validator-expanded-deterministic-guards is apply-ready.`

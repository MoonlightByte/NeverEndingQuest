## Builder Execution Prompts - prompt-validator-telemetry-and-truth-pack

Use this guide with `tasks.md`. Execute in order and verify after each prompt.

---

## Prompt 1 - Tests and Helper Contracts

Implement tasks 1.1 through 1.3 only.

Goal:
- Lock telemetry and truth-pack contracts before changing runtime logic.

Scope:
- new focused tests, for example:
  - `scripts/test_validation_routing_telemetry.py`
  - `scripts/test_validator_truth_pack.py`

Required:
- Add tests for deterministic skip/compression telemetry shape and reason codes.
- Add tests for touched-character truth-pack fields and conditional inventory inclusion.
- Add source-contract tests for `main.py` integration points.
- Do not edit runtime yet except if a tiny import/path fix is required for the tests to run.

Verify:
```bash
python3 -m py_compile scripts/test_validation_routing_telemetry.py scripts/test_validator_truth_pack.py
python3 scripts/test_validation_routing_telemetry.py
python3 scripts/test_validator_truth_pack.py
```

Report:
- exact telemetry fields locked by tests
- exact truth-pack fields locked by tests
- PASS/FAIL for all verification commands

---

## Prompt 2 - Routing Telemetry

Implement tasks 2.1 through 2.3 only.

Scope:
- `utils/validation_routing.py`
- `main.py`

Required:
- Extend routing helpers to expose deterministic telemetry fields.
- Wire telemetry into validation flow in `main.py`.
- Keep changes additive and low-overhead.

Verify:
```bash
python3 -m py_compile utils/validation_routing.py main.py scripts/test_validation_routing_telemetry.py
python3 scripts/test_validation_routing_telemetry.py
```

---

## Prompt 3 - Touched-Character Truth Pack

Implement tasks 3.1 through 3.3 only.

Scope:
- new helper under `utils/` or `core/validation/`
- focused tests

Required:
- Build compact mechanical truth packs for touched characters.
- Include mechanics-first fields.
- Include inventory only when the touched change is inventory-relevant or ambiguous.

Verify:
```bash
python3 -m py_compile utils/validator_truth_pack.py scripts/test_validator_truth_pack.py
python3 scripts/test_validator_truth_pack.py
```

---

## Prompt 4 - Validation Context Integration

Implement tasks 4.1 and 4.2 only.

Scope:
- `main.py`

Required:
- Replace or reduce the current touched-character inventory-heavy validation context with truth-pack output.
- Preserve fail-open behavior if truth-pack assembly fails.

Verify:
```bash
python3 -m py_compile main.py utils/validator_truth_pack.py
python3 scripts/test_validation_routing_telemetry.py
python3 scripts/test_validator_truth_pack.py
```

---

## Prompt 5 - Final Verification

Implement tasks 5.1 and 5.2.

Verify:
```bash
python3 -m py_compile main.py utils/validation_routing.py utils/validator_truth_pack.py scripts/test_validation_routing_telemetry.py scripts/test_validator_truth_pack.py
python3 scripts/test_validation_routing_telemetry.py
python3 scripts/test_validator_truth_pack.py
openspec validate prompt-validator-telemetry-and-truth-pack
```

Ready signal:
- "prompt-validator-telemetry-and-truth-pack is apply-ready."

## Builder Execution Prompts - prompt-validator-runtime-authority-and-performance

Use this guide with `tasks.md`. Execute in order and verify after each prompt.

---

## Prompt 1 - Runtime Prompt Authority

Implement tasks 1.1 through 1.3 only.

Goal:
- Establish compressed prompt authority in live narrator/runtime paths before changing performance logic.

Scope:
- `main.py`
- `core/ai/conversation_utils.py`
- new focused tests, for example `scripts/test_runtime_prompt_authority.py`

Required:
- Add tests proving the live narrator path loads `prompts/system_prompt_compressed.txt`.
- Add tests proving conversation history prompt identity uses the compressed narrator prompt.
- Update runtime loader paths accordingly.
- Do not change validation compression or routing yet.

Verify:
```bash
python3 -m py_compile main.py core/ai/conversation_utils.py scripts/test_runtime_prompt_authority.py
python3 scripts/test_runtime_prompt_authority.py
```

Report:
- exact runtime call sites changed
- PASS/FAIL for both verification commands

---

## Prompt 2 - Thresholded Validation Compression

Implement tasks 2.1 through 2.3 only.

Scope:
- `main.py`
- focused tests for threshold behavior

Required:
- Add threshold-based compression routing tests first.
- Replace unconditional validation compression with threshold-based logic.
- Preserve fail-open behavior if compression fails.

Verify:
```bash
python3 -m py_compile main.py scripts/test_runtime_prompt_authority.py scripts/test_validation_compression_routing.py
python3 scripts/test_validation_compression_routing.py
```

---

## Prompt 3 - Low-Risk Validation Skip Routing

Implement tasks 3.1 through 3.3 only.

Scope:
- `main.py`
- new focused routing tests

Required:
- Add conservative routing helper tests first.
- Implement skip path only for narrow low-risk cases.
- Keep high-risk actions on full validator path.

Verify:
```bash
python3 -m py_compile main.py scripts/test_validation_skip_routing.py
python3 scripts/test_validation_skip_routing.py
```

---

## Prompt 4 - Compressed Narrator Prompt Reorder

Implement tasks 4.1 through 4.3 only.

Scope:
- `prompts/system_prompt_compressed.txt`
- prompt-order tests

Required:
- Add tests for `@RESOLUTION_LADDER` presence and hard-rules-first order.
- Reorder and slim compressed prompt without changing covered action contracts.

Verify:
```bash
python3 scripts/test_runtime_prompt_authority.py
python3 scripts/test_narrator_prompt_structure.py
```

---

## Prompt 5 - Final Verification

Implement tasks 5.1 and 5.2.

Verify:
```bash
python3 -m py_compile main.py core/ai/conversation_utils.py scripts/test_runtime_prompt_authority.py scripts/test_validation_compression_routing.py scripts/test_validation_skip_routing.py scripts/test_narrator_prompt_structure.py
python3 scripts/test_runtime_prompt_authority.py
python3 scripts/test_validation_compression_routing.py
python3 scripts/test_validation_skip_routing.py
python3 scripts/test_narrator_prompt_structure.py
openspec validate prompt-validator-runtime-authority-and-performance
```

Ready signal:
- "prompt-validator-runtime-authority-and-performance is apply-ready."

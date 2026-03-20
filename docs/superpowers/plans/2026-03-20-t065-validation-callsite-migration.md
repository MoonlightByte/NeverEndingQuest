# T065 Validation Callsite Migration

> **ALL coding changes must be done by hand -- one file at a time, verified individually.**

**Goal:** Migrate T065 (AI response validation) to use per-provider model configs.

**Architecture:** Same pattern as T067 -- named config dicts in model_config.py,
callsite branches on MODEL_PROVIDER.

---

## Capture Testing + Manual Validation Results

| Model | Correct | Quality Avg | Avg Cost | Avg Latency | vs Baseline |
|---|---|---|---|---|---|
| gpt-5.2\|low | 9/9 manual + 4/5 capture | 4.70 | $0.0166 | 3.9s | +29% |
| gemini-3-flash\|medium | 3/3 manual + 4/5 capture | 4.93 | $0.0035 | 9.0s | -73% |
| gemini-3.1-flash-lite\|medium | 3/3 manual | N/A | N/A | 1.6s | N/A |
| gpt-4.1 baseline | 4/5 capture | 4.66 | $0.0129 | 2.0s | baseline |
| gpt-5.2\|none | **0/15 manual** | 3.50 | $0.0126 | 3.1s | **UNUSABLE** |

**Selected models:**
- **OpenAI:** gpt-5.2 with reasoning_effort="low" (needs reasoning for validation)
- **Gemini:** gemini-3-flash-preview with thinking_level="medium" (capture tested: 4.93 quality, 5/5 correct v2)
- **Legacy:** gpt-4.1-2025-04-14 (no extra params)
- **LM Studio:** local-model (no extra params)

**Key insight:** This callsite CANNOT use reasoning_effort="none" -- validation
requires reasoning to analyze the DM response against game rules. Temperature
is 0.1 (low for consistency) and gets stripped for gpt-5.2 at reasoning > none.

---

### Task 1: Add T065 Model Configs to model_config.py

**Files:**
- Modify: `model_config.py`

- [ ] **Step 1: Add 4 config dicts after the T067 configs**

```python
# --- T065 AI Response Validation Model Configs (from capture + manual testing) ---
# Validation requires reasoning -- gpt-5.2|none is UNUSABLE (0/15 correct).
# Temperature is 0.1 at callsite (stays there, not in config).

# OpenAI (reasoning=low required for validation accuracy)
DM_VALIDATION_GPT52_LOW = {"model": "gpt-5.2", "reasoning_effort": "low"}

# Gemini (3-flash with medium thinking -- capture tested: 4.93 quality, 5/5 correct)
DM_VALIDATION_GEMINI_FLASH_MEDIUM = {"model": "gemini-3-flash-preview", "thinking_level": "medium"}

# Legacy (no extra params)
DM_VALIDATION_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
DM_VALIDATION_LMSTUDIO = {"model": "local-model"}
```

- [ ] **Step 2: Commit**

```bash
git add model_config.py
git commit -m "feat: add T065 per-provider model configs for validation"
```

---

### Task 2: Migrate T065 Callsite in main.py

**Files:**
- Modify: `main.py:1225-1231`

- [ ] **Step 1: Read the current callsite**

Read `main.py` lines 1225-1231. Current state:
```python
for attempt in range(max_validation_retries):
    validation_result = capture_and_fanout("T065", client.chat.completions.create,
        messages=validation_messages_to_send,
        model=DM_VALIDATION_MODEL,
        temperature=0.1
    )
```

This uses raw `client.chat.completions.create` (not routed through create_completion),
hardcoded `DM_VALIDATION_MODEL`, and `temperature=0.1`.

- [ ] **Step 2: Add provider config selection before the retry loop**

Place this before the `for attempt in range(max_validation_retries):` line:

```python
from model_config import MODEL_PROVIDER
if MODEL_PROVIDER == "openai":
    validation_config = config.DM_VALIDATION_GPT52_LOW
elif MODEL_PROVIDER == "gemini":
    validation_config = config.DM_VALIDATION_GEMINI_FLASH_MEDIUM
elif MODEL_PROVIDER == "lmstudio":
    validation_config = config.DM_VALIDATION_LMSTUDIO
else:  # legacy
    validation_config = config.DM_VALIDATION_LEGACY
```

- [ ] **Step 3: Update the API call inside the loop**

Change from:
```python
    validation_result = capture_and_fanout("T065", client.chat.completions.create,
        messages=validation_messages_to_send,
        model=DM_VALIDATION_MODEL,
        temperature=0.1
    )
```

To:
```python
    validation_result = capture_and_fanout("T065", api_client.create_completion,
        messages=validation_messages_to_send,
        model=validation_config["model"],
        temperature=0.1,
        **{k: v for k, v in validation_config.items() if k != "model"})
```

Note: temperature=0.1 stays at the callsite. For gpt-5.2 with reasoning=low,
_enforce_provider_constraints will strip temperature (reasoning > none).
For legacy, temperature passes through normally.

- [ ] **Step 4: Verify api_client is imported**

Check that `from core.ai import api_client` exists in main.py imports.
If not, add it.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: migrate T065 to per-provider model configs

Validation uses gpt-5.2 reasoning=low (OpenAI), gemini-3-flash
thinking=medium (Gemini). gpt-5.2|none is unusable for validation
(0/15 correct in manual testing)."
```

---

## Summary

| Task | File | Change |
|---|---|---|
| 1 | `model_config.py` | Add 4 T065 config dicts |
| 2 | `main.py` | Wire T065 callsite with per-provider config |

## What This Does NOT Change

- T065 temperature (0.1) -- stays at the callsite
- T065 retry loop -- stays as-is
- Validation message assembly -- unchanged
- Prompts -- frozen

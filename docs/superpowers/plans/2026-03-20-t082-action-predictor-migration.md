# T082 Action Predictor Callsite Migration

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **ALL coding changes must be done by hand -- one file at a time. No automated scripts.**

**Goal:** Migrate T082 (action predictor / model router) to use per-provider model configs.

**Architecture:** Same config-dict pattern as T067/T065. Named config dicts in model_config.py, callsite branches on MODEL_PROVIDER. Temperature 0.1 stays at callsite.

**Tech Stack:** Python, model_config.py, utils/action_predictor.py

---

## Capture Testing Results (16 entries, GPT-5.4 reviewed)

| Provider | Model | Correct | Avg Score | Avg Cost | Avg Latency |
|---|---|---|---|---|---|
| OpenAI | gpt-5-mini reasoning=low | 14/14 | 4.00 | $0.0007 | 2.8s |
| Gemini | gemini-3-flash thinking=minimal | 13/14 | 4.07 | $0.0011 | 1.4s |
| Legacy | gpt-4.1 baseline | 16/16 | 4.19 | $0.0040 | 1.5s |

**Context:** T082 is a binary classifier that fires on EVERY player turn before the
main DM call (T067). It predicts whether the player's input needs game actions (full
model) or is simple conversation (mini model). Speed and cost are critical -- a wrong
prediction just routes to the wrong tier model, not a game-breaking error.

---

## Files Changed

| File | Change |
|---|---|
| `model_config.py` | Add 4 T082 config dicts (reuse GPT5MINI_LOW, new Gemini flash) |
| `utils/action_predictor.py` | Wire callsite with per-provider config, route through api_client |

---

### Task 1: Add T082 Model Configs to model_config.py

**Files:**
- Modify: `model_config.py:75` (after T065 configs)

- [ ] **Step 1: Add 4 config dicts**

Add after the T065 LM Studio config (line 75):

```python
# --- T082 Action Predictor Model Configs (from capture testing) ---
# Binary classifier, fires every turn. Speed and cost critical.
# Temperature is 0.1 at callsite.

# OpenAI (mini model with low reasoning -- 14/14 correct, $0.0007, 2.8s)
ACTION_PRED_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini (3-flash with minimal thinking -- 13/14 correct, $0.0011, 1.4s fastest)
ACTION_PRED_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}

# Legacy (full model, no extra params -- matches current ACTION_PREDICTION_MODEL)
ACTION_PRED_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
ACTION_PRED_LMSTUDIO = {"model": "local-model"}
```

Note: We do NOT reuse `DM_MINI_MODEL_GPT5MINI_LOW` by reference because each
callsite's config should be independently named for clarity and future tuning.
The values happen to be identical but they are separate configs.

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 3: Commit**

```bash
git add model_config.py
git commit -m "feat: add T082 per-provider model configs for action predictor"
```

---

### Task 2: Migrate T082 Callsite in action_predictor.py

**Files:**
- Modify: `utils/action_predictor.py:41-48` (imports)
- Modify: `utils/action_predictor.py:152-158` (API call)

- [ ] **Step 1: Read the current callsite**

Read `utils/action_predictor.py` lines 41-48 and 152-158. Current state:

```python
# Line 42-43: imports
from openai import OpenAI
from config import OPENAI_API_KEY, ACTION_PREDICTION_MODEL

# Line 47-48: client init
client = OpenAI(api_key=OPENAI_API_KEY)

# Line 154-158: API call
response = capture_and_fanout("T082", client.chat.completions.create, messages=[
        {"role": "system", "content": ACTION_PREDICTION_PROMPT},
        {"role": "user", "content": f"Analyze this user input: '{user_input}'"}
    ], model=ACTION_PREDICTION_MODEL,
    temperature=0.1)
```

- [ ] **Step 2: Update imports and remove dead code**

Change lines 42-43 from:
```python
from openai import OpenAI
from config import OPENAI_API_KEY, ACTION_PREDICTION_MODEL
```

To:
```python
import config
from core.ai import api_client
```

Remove the module-level client initialization at lines 47-48:
```python
# DELETE these lines:
# client = OpenAI(api_key=OPENAI_API_KEY)
```

After migration, `OpenAI`, `OPENAI_API_KEY`, `ACTION_PREDICTION_MODEL`, and
`client` are all dead code -- the only use of `client` was the API call we're
replacing. `api_client.create_completion()` handles client creation internally.

- [ ] **Step 3: Add provider config selection before the API call**

Inside the `predict_action_requirement` function, before the try block at line 152,
add the deferred import and provider selection. The import MUST be inside the
function (not module level) so it reads the current provider value each call --
module-level `from model_config import MODEL_PROVIDER` creates a stale snapshot.

```python
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        pred_config = config.ACTION_PRED_GPT5MINI_LOW
    elif MODEL_PROVIDER == "gemini":
        pred_config = config.ACTION_PRED_GEMINI_FLASH_MINIMAL
    elif MODEL_PROVIDER == "lmstudio":
        pred_config = config.ACTION_PRED_LMSTUDIO
    else:  # legacy
        pred_config = config.ACTION_PRED_LEGACY
```

- [ ] **Step 4: Update the API call**

Change lines 154-158 from:
```python
        response = capture_and_fanout("T082", client.chat.completions.create, messages=[
                {"role": "system", "content": ACTION_PREDICTION_PROMPT},
                {"role": "user", "content": f"Analyze this user input: '{user_input}'"}
            ], model=ACTION_PREDICTION_MODEL,
            temperature=0.1)
```

To:
```python
        response = capture_and_fanout("T082", api_client.create_completion,
            messages=[
                {"role": "system", "content": ACTION_PREDICTION_PROMPT},
                {"role": "user", "content": f"Analyze this user input: '{user_input}'"}
            ],
            model=pred_config["model"],
            temperature=0.1,
            **{k: v for k, v in pred_config.items() if k != "model"})
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 6: Commit**

```bash
git add utils/action_predictor.py
git commit -m "feat: migrate T082 to per-provider model configs

Action predictor now uses gpt-5-mini reasoning=low (OpenAI),
gemini-3-flash thinking=minimal (Gemini). 83% cost reduction
vs baseline with 14/14 correct (OpenAI) and 13/14 (Gemini)."
```

---

## Summary

| Task | File | Change |
|---|---|---|
| 1 | `model_config.py` | Add 4 T082 config dicts |
| 2 | `utils/action_predictor.py` | Wire callsite with per-provider config |

## What This Does NOT Change

- T082 temperature (0.1) -- stays at callsite
- T082 system prompt (ACTION_PREDICTION_PROMPT) -- frozen
- T082 response parsing logic -- unchanged
- T082 fallback behavior on error -- unchanged

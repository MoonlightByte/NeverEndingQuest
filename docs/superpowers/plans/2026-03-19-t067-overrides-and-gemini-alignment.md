# T067 Migration + Infrastructure Fixes (v5)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **ALL coding changes must be done by hand -- one file at a time, verified individually. No automated scripts or bulk operations.**

**Goal:** Migrate T067 (main DM loop) to use per-provider model configs with explicit params, fix two infrastructure bugs, and remove the blanket escalation ladder.

**Architecture:** Each model+params combo from capture testing becomes a named config variable in `model_config.py`. The callsite checks `MODEL_PROVIDER` and references the exact config variable per provider. Temperature stays at the callsite. `create_completion()` is a thin router that does NOT inject params.

**Tech Stack:** Python, model_config.py, api_client.py, gemini_caller.py, main.py

---

## T067 Capture Testing Results (6 entries, GPT-scored)

| Provider | Tier | Winner | Quality | Cost | Config |
|---|---|---|---|---|---|
| OpenAI | Full | gpt-5.2\|none | 4.75 | $0.0274 | `{"model": "gpt-5.2", "reasoning_effort": "none"}` |
| OpenAI | Mini | gpt-5-mini\|low | 4.67 | $0.0046 | `{"model": "gpt-5-mini", "reasoning_effort": "low"}` |
| Gemini | Full | untested 3.1, conservative | TBD | TBD | `{"model": "gemini-3.1-pro-preview", "thinking_level": "low"}` |
| Gemini | Mini | untested 3.1, flash\|minimal won for 3.0 | TBD | TBD | `{"model": "gemini-3.1-flash-lite-preview", "thinking_level": "minimal"}` |
| Legacy | Full | gpt-4.1 (baseline) | 4.67 | $0.0293 | `{"model": "gpt-4.1-2025-04-14"}` |
| Legacy | Mini | gpt-4.1-mini (baseline) | 4.67 | $0.0056 | `{"model": "gpt-4.1-mini-2025-04-14"}` |
| LM Studio | Full | local passthrough | N/A | $0 | `{"model": "local-model"}` |
| LM Studio | Mini | local passthrough | N/A | $0 | `{"model": "local-model"}` |

---

### Task 1: Fix `model_supports_thinking()` for Gemini 3.1 Models

**Why first:** Without this fix, thinking_level params are silently dropped for 3.1 models
in both capture and runtime paths. Must be fixed before T067 can use gemini 3.1.

**Files:**
- Modify: `utils/capture/gemini_caller.py:31-35`

- [ ] **Step 1: Add 3.1 model prefixes to the allowlist**

Change lines 31-35 from:
```python
THINKING_SUPPORTED_MODELS = [
    "gemini-2.0-flash-thinking",
    "gemini-3-flash",
    "gemini-3-pro",
]
```

To:
```python
THINKING_SUPPORTED_MODELS = [
    "gemini-2.0-flash-thinking",
    "gemini-3-flash",
    "gemini-3-pro",
    "gemini-3.1-pro",
    "gemini-3.1-flash",
]
```

Both the capture path (`gemini_caller.py:210`) and runtime path (`api_client.py:318`)
import this same function -- one fix covers both.

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

Expected: All tests pass (additive change).

- [ ] **Step 3: Commit**

```bash
git add utils/capture/gemini_caller.py
git commit -m "fix: add gemini-3.1 models to thinking_config allowlist"
```

---

### Task 2: Fix `_enforce_provider_constraints` for gpt-5-mini

**Why:** If any callsite passes `reasoning_effort="none"` for gpt-5-mini, the API
returns a 400 error. Mini doesn't support "none". Clamp to "low" (the capture
testing winner for mini, and "minimal" is a Gemini-only term per the reference docs).

**Files:**
- Modify: `core/ai/api_client.py:231-248`

- [ ] **Step 1: Add reasoning_effort guard for gpt-5-mini**

In `_enforce_provider_constraints`, change the mini block from:
```python
        if "mini" in model_lower and "5" in model_lower:
            kwargs["_strip_temperature"] = True
```

To:
```python
        if "mini" in model_lower and "5" in model_lower:
            kwargs["_strip_temperature"] = True
            # gpt-5-mini does not support reasoning_effort="none"
            if reasoning and str(reasoning).lower() == "none":
                kwargs["reasoning_effort"] = "low"
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 3: Commit**

```bash
git add core/ai/api_client.py
git commit -m "fix: clamp reasoning_effort=none to low for gpt-5-mini"
```

---

### Task 3: Remove Blanket Escalation Ladder from `create_completion()`

**Why:** The escalation ladder injects reasoning_effort/thinking_level into EVERY call,
even when the callsite never asked for it. `create_completion()` must be a thin router.
Callsites own their params -- they pass them explicitly via the config dict pattern.

Only T013 and T067 are migrated through `create_completion()`. T013 is a utility call
that works fine without injected params. All other callsites still use raw
`client.chat.completions.create` and are unaffected.

**Files:**
- Modify: `core/ai/api_client.py`
- Modify: `tests/test_create_completion_integration.py`

- [ ] **Step 1: Remove the escalation + override merge block**

Replace lines 191-215 (from `# --- Clamp retry_attempt ---` through the
`kwargs[key] = val` loop) with:

```python
    # create_completion() is a thin routing layer. It does NOT inject
    # reasoning_effort, thinking_level, or other params. The callsite
    # owns its parameters via named config dicts in model_config.py.
```

- [ ] **Step 2: Remove dead code**

Remove from `api_client.py`:
- `_ESCALATION_LADDERS` dict (lines ~78-120)
- `_get_ladder_key()` function (lines ~123-139)
- `CALLSITE_OVERRIDES` from the import at line 184 (change to `from model_config import MODEL_PROVIDER`)

- [ ] **Step 3: Update docstring**

Update `create_completion()` docstring (around line 156) to say it does two things:
1. Route to the correct provider API
2. Translate parameters natively for that provider

Remove any mention of escalation or retry_attempt escalation behavior.

- [ ] **Step 4: Update stale comment in `_gemini_completion`**

Line 317: change `# Thinking level (from escalation ladder or explicit kwarg)` to
`# Thinking level (from callsite kwarg)`

- [ ] **Step 5: Update tests**

Remove or rewrite these test classes that test removed behavior:
- `TestEscalationLadders` (~12 methods)
- `TestRetryAttemptClamping`
- `TestCallsiteOverrides`
- Remove `_get_ladder_key, _ESCALATION_LADDERS` from the import at line 18

Run tests after changes:
```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 6: Commit**

```bash
git add core/ai/api_client.py tests/test_create_completion_integration.py
git commit -m "refactor: remove blanket escalation ladder from create_completion

create_completion() is a thin routing layer. Callsites own their
model selection and params via named config dicts."
```

---

### Task 4: Add T067 Model Configs to `model_config.py`

**Why:** T067 needs named config variables for each provider's model+params combo.

**Files:**
- Modify: `model_config.py`

- [ ] **Step 1: Add the 8 config variables**

Add after the existing model variables section:
```python
# --- T067 Main DM Loop Model Configs (from capture testing) ---
# Each dict bundles model string + provider-specific params.
# Temperature is NOT included -- it stays at the callsite.

# OpenAI
DM_FULL_MODEL_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
DM_MINI_MODEL_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini (3.1 models - conservative params until capture data collected)
DM_FULL_MODEL_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
DM_MINI_MODEL_GEMINI_FLASH_MINIMAL = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "minimal"}

# Legacy (no extra params)
DM_FULL_MODEL_LEGACY = {"model": "gpt-4.1-2025-04-14"}
DM_MINI_MODEL_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}

# LM Studio (local passthrough - no extra params, routes through OpenAI client to localhost)
DM_FULL_MODEL_LMSTUDIO = {"model": "local-model"}
DM_MINI_MODEL_LMSTUDIO = {"model": "local-model"}
```

- [ ] **Step 2: Commit**

```bash
git add model_config.py
git commit -m "feat: add T067 per-provider model configs from capture testing"
```

---

### Task 5: Migrate T067 Callsite in `main.py`

**Why:** Wire T067 to use the new config variables per provider.

**Files:**
- Modify: `main.py:2225-2318`

- [ ] **Step 1: Read the current callsite**

Read `main.py` lines 2225-2318 to understand:
- Line 2231: intelligent routing picks DM_MINI_MODEL or DM_FULL_MODEL
- Line 2238: retries force DM_FULL_MODEL
- Line 2307-2309: retry >= 4 also forces DM_FULL_MODEL
- Line 2313-2318: the API call with selected_model, TEMPERATURE, retry_attempt

- [ ] **Step 2: Add provider-based config selection AFTER line 2309**

Place this block between the retry >= 4 override (line 2309) and the API call
(line 2313), so `selected_model` has its final value including any retry overrides:

Use the existing `from model_config import MODEL_PROVIDER` import at line 2311.
Do NOT add a duplicate import.

```python
if MODEL_PROVIDER == "openai":
    full_config = config.DM_FULL_MODEL_GPT52_NONE
    mini_config = config.DM_MINI_MODEL_GPT5MINI_LOW
elif MODEL_PROVIDER == "gemini":
    full_config = config.DM_FULL_MODEL_GEMINI_PRO_LOW
    mini_config = config.DM_MINI_MODEL_GEMINI_FLASH_MINIMAL
elif MODEL_PROVIDER == "lmstudio":
    full_config = config.DM_FULL_MODEL_LMSTUDIO
    mini_config = config.DM_MINI_MODEL_LMSTUDIO
else:  # legacy
    full_config = config.DM_FULL_MODEL_LEGACY
    mini_config = config.DM_MINI_MODEL_LEGACY

if selected_model == config.DM_MINI_MODEL:
    selected_config = mini_config
else:
    selected_config = full_config
```

- [ ] **Step 3: Update the API call**

Change lines 2313-2318 from:
```python
response = capture_and_fanout("T067", api_client.create_completion,
    messages=messages_to_send,
    model=selected_model,
    temperature=TEMPERATURE,
    retry_attempt=validation_retry_count
)
```

To:
```python
response = capture_and_fanout("T067", api_client.create_completion,
    messages=messages_to_send,
    model=selected_config["model"],
    temperature=TEMPERATURE,
    **{k: v for k, v in selected_config.items() if k != "model"})
```

Temperature stays at the callsite. `retry_attempt` is removed (ladder gone).
Provider-specific params (reasoning_effort, thinking_level) come from the config dict.

- [ ] **Step 4: Run the game and verify**

Start with legacy provider, verify T067 works normally.
Switch to openai in settings, verify calls go through.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: migrate T067 to per-provider model configs

T067 now explicitly selects model+params per provider from named
config variables. Legacy stays on gpt-4.1, OpenAI uses gpt-5.2
with reasoning_effort=none, Gemini uses 3.1-pro with thinking=low,
LM Studio uses local-model."
```

---

### Task 6: Merge Capture Config Pricing

**Files:**
- Modify: `/mnt/c/dungeon_master_v1/model_captures/capture_config.json`

- [ ] **Step 1: Read both capture configs and add missing pricing**

Add `model_pricing` section to main repo config if missing.
Do NOT overwrite -- main repo has gpt-5.4 variants and gpt-4.1 baselines
that testing folder lacks.

- [ ] **Step 2: No commit** (capture_config.json is gitignored)

---

## Summary

| Task | File | Change |
|---|---|---|
| 1 | `utils/capture/gemini_caller.py` | Add gemini-3.1 to thinking allowlist |
| 2 | `core/ai/api_client.py` | Clamp reasoning_effort=none to low for gpt-5-mini |
| 3 | `core/ai/api_client.py` + tests | Remove blanket escalation ladder + dead code |
| 4 | `model_config.py` | Add 8 named model config dicts for T067 |
| 5 | `main.py` | Wire T067 callsite to use per-provider configs |
| 6 | `capture_config.json` | Merge pricing (don't overwrite) |

## What This Does NOT Change

- T067 temperature (0.8) -- stays at the callsite
- T067 intelligent routing logic (mini vs full selection) -- stays as-is
- Prompts -- frozen per project rules
- Other callsites -- only T067 is migrated in this plan (T013 already done)

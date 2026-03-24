# T017 Combat Compression Callsite Migration

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **ALL coding changes must be done by hand -- one file at a time. No automated scripts.**

**Goal:** Migrate T017 (combat message compression) to per-provider model configs with v5 prompt improvements.

**Architecture:** Same config-dict pattern. CRITICAL: this callsite outputs plain text tags (`@T=CS/v2`), NOT JSON. Must pass `response_format=None` to opt out of default JSON mode. The system prompt was improved during testing (v5) with explicit PLAYER TURN, ROUND COMPLETE, and @STATUS rules.

**Tech Stack:** Python, model_config.py, combat_compression_engine.py

---

## Testing Results

**Synthetic testing (6 entries, v5 prompt, all models tested across 5 iterations):**

| Model | Correct/Acceptable | Avg Latency | Key Finding |
|---|---|---|---|
| gpt-4.1-mini baseline | 6/6 | 3.2s | Perfect but being sunset |
| gpt-5-mini\|low | 5/6 | 15.5s | Entry 4 @ROUND off by 1 (minor for AI context) |
| gpt-5-mini\|minimal | 4/6 | 4.5s | Entries 4,5 structural failures |
| gpt-5-mini\|medium | 0/6 | 44.7s | Worse than low -- @DICE missing entirely |
| gemini-3-flash\|low | 6/6 | 2.0s | Stable, all correct/minor |
| gemini-3-flash\|minimal | 6/6 run1, 4/6 run2 | 1.9s | Unstable between runs |

**Selected models:**
- **OpenAI:** gpt-5-mini reasoning_effort="low" (5/6, entry 4 @ROUND cosmetic only)
- **Gemini:** gemini-3-flash-preview thinking_level="low" (stable 6/6, 2.0s, fastest)
- **Legacy:** gpt-4.1-mini (unchanged)
- **LM Studio:** local-model

**CRITICAL:** `response_format=None` required for all providers (plain text output).

---

## Files Changed

| File | Change |
|---|---|
| `core/ai/combat_compression_engine.py` | v5 prompt improvements already made; wire callsite with per-provider config; remove dead OpenAI client |
| `model_config.py` | Add 4 T017 config dicts with response_format=None |
| `tests/model_validation/test_t017_compression.py` | NEW -- synthetic testing script |
| `tests/model_validation/README.md` | Add T017 to scripts + migration status |
| `docs/reference/legacy-model-variable-map.md` | Mark T017 done |

---

### Task 1: Add T017 Model Configs to model_config.py

**Files:**
- Modify: `model_config.py` (after T079 configs)

- [ ] **Step 1: Add 4 config dicts**

```python
# --- T017 Combat Compression Model Configs (from synthetic testing v5 prompt) ---
# CRITICAL: This callsite outputs plain text tags (@T=CS/v2), NOT JSON.
# response_format=None opts out of default JSON mode.
# Temperature is 0.3 at callsite.

# OpenAI (mini model with low reasoning -- 5/6 correct, entry 4 @ROUND cosmetic only)
COMBAT_COMPRESS_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low", "response_format": None}

# Gemini (3-flash with low thinking -- stable 6/6, 2.0s avg, fastest)
COMBAT_COMPRESS_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low", "response_format": None}

# Legacy (no extra params)
COMBAT_COMPRESS_LEGACY = {"model": "gpt-4.1-mini-2025-04-14", "response_format": None}

# LM Studio (local passthrough)
COMBAT_COMPRESS_LMSTUDIO = {"model": "local-model", "response_format": None}
```

Note: ALL configs include `response_format=None` to opt out of JSON mode.
The dict unpacking passes this through to `create_completion()` which uses
the `_UNSET` sentinel pattern -- `None` means "plain text, no JSON mode."

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 3: Commit**

```bash
git add model_config.py
git commit -m "feat: add T017 per-provider model configs for combat compression"
```

---

### Task 2: Migrate T017 Callsite and Commit v5 Prompt

**Files:**
- Modify: `core/ai/combat_compression_engine.py`

The v5 prompt improvements (PLAYER TURN, ROUND COMPLETE, @STATUS precedence rules)
are already in the file from testing. This task wires the callsite and cleans up
dead code. The `.bak` backup file should be removed after commit.

- [ ] **Step 1: Update imports**

Change line 14 and add imports:
```python
# Replace:
from openai import OpenAI

# With:
import config
from core.ai import api_client
```

Keep `from model_config import NARRATIVE_COMPRESSION_MODEL` at line 22 for now
(other code may reference it).

- [ ] **Step 2: Replace client/model setup in __init__ with provider config selection**

In `CombatCompressor.__init__()`, remove the api_key handling and client setup
(lines 119-137: everything from `def __init__` through `self.model = NARRATIVE_COMPRESSION_MODEL`).

PRESERVE lines 138-140 (`self.enable_caching`, `self.cache_file`, `self.cache`) --
these are the caching setup and MUST NOT be removed.

Replace the removed block with:
```python
    def __init__(self, enable_caching: bool = True):
        """Initialize compressor."""
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            self._config = config.COMBAT_COMPRESS_GPT5MINI_LOW
        elif MODEL_PROVIDER == "gemini":
            self._config = config.COMBAT_COMPRESS_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            self._config = config.COMBAT_COMPRESS_LMSTUDIO
        else:  # legacy
            self._config = config.COMBAT_COMPRESS_LEGACY
```

Note: `api_key` parameter removed from signature (create_completion handles clients).
The deferred import is inside `__init__`, not module level, because
`CombatCompressor` is instantiated per-use (not at import time).
Lines 138-140 (self.enable_caching, self.cache_file, self.cache) follow immediately after.

- [ ] **Step 3: Update the API call AND all self.model references**

Change the debug print at line 181 from:
```python
            print(f"[DEBUG] Calling AI compression with model: {self.model}")
```
To:
```python
            print(f"[DEBUG] Calling AI compression with model: {self._config['model']}")
```

Change lines 182-185 from:
```python
            response = capture_and_fanout("T017", self.client.chat.completions.create, messages=[
                    {"role": "system", "content": COMBAT_COMPRESSION_PROMPT},
                    {"role": "user", "content": content}
                ], model=self.model, temperature=0.3)
```

To:
```python
            response = capture_and_fanout("T017", api_client.create_completion,
                messages=[
                    {"role": "system", "content": COMBAT_COMPRESSION_PROMPT},
                    {"role": "user", "content": content}
                ],
                model=self._config["model"],
                temperature=0.3,
                **{k: v for k, v in self._config.items() if k != "model"})
```

Also update the error log at line ~223 from:
```python
            print(f"[ERROR] Model: {self.model}")
```
To:
```python
            print(f"[ERROR] Model: {self._config['model']}")
```

Grep for any remaining `self.model` references in the file and update them
to `self._config["model"]`. Do NOT change `self._config` references or the
`NARRATIVE_COMPRESSION_MODEL` import (used elsewhere at line 406).

This unpacks `reasoning_effort`/`thinking_level` AND `response_format=None`
from the config dict. The `response_format=None` flows through to
`create_completion()` which handles it via the `_UNSET` sentinel pattern
(None = plain text, skip JSON mode).

- [ ] **Step 4: Remove backup file**

```bash
rm core/ai/combat_compression_engine.py.bak
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 6: Commit**

```bash
git add core/ai/combat_compression_engine.py
git commit -m "feat: migrate T017 to per-provider model configs + v5 prompt

Combat compression now uses gpt-5-mini reasoning=low (OpenAI),
gemini-3-flash thinking=low (Gemini). All configs pass
response_format=None (plain text tags, not JSON).

Prompt v5 improvements: explicit PLAYER TURN @PROCESS rule,
@STATUS precedence (dead>acted>after_player>waiting),
@ATK mandatory with player:[] convention."
```

---

### Task 3: Save Synthetic Testing Script

**Files:**
- Create: `tests/model_validation/test_t017_compression.py`
- Modify: `tests/model_validation/README.md`

- [ ] **Step 1: Create the test script**

Save a script that replays all 6 captured combat inputs through candidate models
and validates output format (`@T=CS/v2` prefix, no JSON wrapping, no narration).

The script should:
- Load prompts from `model_captures/T017.json`
- Load the system prompt from `combat_compression_engine.py`
- Test baseline, gpt-5-mini|low, and gemini-3-flash|low (no JSON mode)
- Report correct/incorrect per entry with latency
- Support `--model` flag to test a single model

- [ ] **Step 2: Add to README scripts table**

```
| `test_t017_compression.py` | T017 (combat compression) | Plain text tag compression across models, no JSON mode | gpt-5-mini\|low=5/6, gemini-flash\|low=6/6. response_format=None required. |
```

- [ ] **Step 3: Add to migration status table**

```
| T017 | Combat compression | gpt-5-mini low | gemini-3-flash low + response_format=None | Done |
```

- [ ] **Step 4: Mark T017 in legacy map**

Mark NARRATIVE_COMPRESSION_MODEL T017 as done.

- [ ] **Step 5: Commit**

```bash
git add -f tests/model_validation/test_t017_compression.py tests/model_validation/README.md
git add -f docs/reference/legacy-model-variable-map.md
git commit -m "feat: add T017 synthetic test script and update tracking docs"
```

---

## Summary

| Task | File | Change |
|---|---|---|
| 1 | `model_config.py` | Add 4 T017 config dicts with response_format=None |
| 2 | `combat_compression_engine.py` | Wire callsite + commit v5 prompt improvements |
| 3 | Test script + tracking docs | Save test script, update README and legacy map |

## What This Does NOT Change

- T017 temperature (0.3) -- stays at callsite
- T017 caching logic -- unchanged
- T017 output validation (`@T=CS/v2` prefix check) -- unchanged
- T017 code fence stripping -- unchanged

## Important Notes

- This is the first callsite using `response_format=None` in the config dict
- The v5 prompt changes are backwards-compatible with gpt-4.1-mini (baseline still works 6/6)
- The `.bak` file from prompt testing should be removed after commit

# OpenRouter LLM Router Architecture Plan

## Executive Summary

**Objective:** Centralize 82 LLM call sites across 44 files behind a single `llm.call()` interface. The router is a thin facade (~200 lines) over the existing `ai_client_factory.py` infrastructure, adding cost tracking and JSON retry logic.

**Status:** PLANNING PHASE - Ready for Phase 1 implementation

**Timeline:** 7-9 days total
- Phase 1: Router Facade (1-2 days)
- Phase 2: File Migration (4-5 days)
- Phase 3: Cleanup & Polish (1-2 days)

**Foundation:** `ai_client_factory.py` already provides provider selection, 3-tier model routing, and fallback logic. This plan builds on that — it does not replace it.

**Current Priority:** The codebase is reverted to OpenAI as LLM provider. The incomplete OpenRouter migration code remains in place but is inactive (`LLM_PROVIDER = "openai"`). The immediate priority is finalizing the Tabletop Mode build and pushing to a personal fork for testers. This router plan will be implemented **after** the OpenAI-based TT build is stable and shipped.

## Titan v2 Alignment Stub

- Umbrella reference: `plans/version-2/titan-integration.md`
- Retune status: Pending (Titan task profile not yet added)
- Last tagged: 2026-02-26
- Retune focus: dedicated Titan task routing to free-thinking profile with isolated budgets and fail-open behavior

---

## Current State Analysis

### Codebase Audit (2026-02-08)

| Metric | Count |
|--------|-------|
| Total `chat.completions.create` call sites | **82** |
| Total files with LLM calls | **44** |
| Direct `OpenAI()` instantiations (excluding factory) | **33** |
| Files using `ai_client_factory` | **13** |
| Files using `get_model_config()` (full 3-tier routing) | **5** |
| Files still using raw `OpenAI()` | **29** |
| Dead code in factory (`get_model_for_task`, etc.) | **3 functions** |

### Migration State

| State | Files | Description |
|-------|-------|-------------|
| **Fully migrated** | 5 | Use `create_chat_client()` + `get_model_config()` |
| **Partially migrated** | 8 | Use `create_chat_client()` but hardcode model constants |
| **Unmigrated** | 29 | Raw `OpenAI(api_key=...)` + hardcoded model constants |
| **Non-chat (skip)** | 2 | Image gen + TTS in `web_interface.py` (Phase 2 scope) |

### Existing Infrastructure (What We Keep)

These components in `ai_client_factory.py` are working and tested:

- `create_chat_client(use_fallback)` — Creates OpenAI or OpenRouter client based on config
- `_get_actual_provider()` — Single source of truth for provider detection
- `get_model_config(task_id)` — 3-tier routing: Kimi thinking toggle / dual model / OpenAI fallback
- `handle_provider_error()` — Fallback detection and user notification
- `get_fallback_notification()` — User-facing fallback message

These components in `model_config.py` are working and tested:

- `THINKING_ENABLED_TASKS` — 16 tasks classified by complexity (to be renamed `COMPLEX_TASKS`)
- `TASK_TEMPERATURES` — Per-task temperature settings
- `TASK_OVERRIDES` — Per-task model override mechanism (exists, currently empty)
- `OPENROUTER_STRATEGY` — Strategy toggle (to be deprecated, replaced by `MODEL_PROFILES`)

### Known Bug: `extra_body` Shape Inconsistency in Factory

**Must fix in `ai_client_factory.py` before router implementation.**

`get_model_config()` returns inconsistent shapes for `extra_body` depending on the code path:

| Path | `extra_body` value | After `api_params.update(extra)` |
|------|-------------------|--------------------------------|
| TIER 1 (kimi_thinking) | `{"thinking": {"type": "enabled"}}` | Adds `thinking` as top-level kwarg |
| TASK_OVERRIDES | `{"extra_body": {"thinking": {"type": "enabled"}}}` | Adds `extra_body` as top-level kwarg |
| OpenAI / fallback | `{}` | No extra kwargs |

Only the TASK_OVERRIDES shape is correct for the OpenAI Python SDK (which expects `extra_body` as a named parameter). The TIER 1 shape would cause `TypeError: Completions.create() got an unexpected keyword argument 'thinking'`.

**This bug has never manifested** because `LLM_PROVIDER` defaults to `"openai"`, so `get_model_config()` always returns `extra_body: {}` and the OpenRouter code paths have never been exercised.

**Short-term fix:** Normalize all paths to `{"extra_body": {"thinking": {"type": ...}}}` shape.

**Long-term fix (this plan):** The router bypasses `get_model_config()` for param generation entirely. `MODEL_PROFILES` provides model-specific params via `complex_params`/`simple_params` fields. The factory's `extra_body` handling becomes irrelevant — the router applies profile params directly and pops `extra_body` on fallback.

### What's Missing (What the Router Adds)

1. **Unified call interface** — Callers must manually create client + build params + handle errors + extract content
2. **Cost tracking** — No token/cost tracking exists anywhere
3. **JSON retry logic** — No structured output parsing with retry
4. **Thread-safe statistics** — Existing `_fallback_status` lacks thread safety

---

## Architecture Overview

### Design Principle: Facade Over Factory

```
Callers (44 files)
       |
       v
  llm_router.py        <-- NEW: Thin facade (~250 lines)
  - call()                  Unified interface
  - _get_profile_and_model  Profile-based routing (model-agnostic)
  - cost tracking           Thread-safe usage stats
  - JSON retry              3-attempt structured output parsing
  - error classification    Hard stop on quota, retry on transient
       |
       v
  ai_client_factory.py  <-- EXISTING: Infrastructure (536 lines)
  - create_chat_client()    Provider-agnostic client creation
  - _get_actual_provider()  Provider detection
  - handle_provider_error() Fallback logic
       |
       v
  model_config.py        <-- EXISTING + NEW: Configuration
  - MODEL_PROFILES          Per-model capability profiles (NEW)
  - COMPLEX_TASKS           Task complexity classification (renamed)
  - TASK_TEMPERATURES       Per-task temperature
  - TASK_OVERRIDES          Per-task model/profile override
```

### Consumer Interface

```python
from utils.llm_router import llm

# Simple text response
result = llm.call(task="dm_main", messages=prompt)

# With temperature override
result = llm.call(task="combat_main", messages=prompt, temperature=0.5)

# Structured JSON output with retry
data = llm.call(task="encounter_update", messages=prompt, json_output=True)

# Check cost so far
stats = llm.get_usage_stats()
```

### Model Agnosticism via Profiles

**Core principle:** The router must not be locked to any specific model. Models evolve, pricing changes, new providers appear. Swapping the active model should be a config-only change — no code modifications.

**Problem:** Different models have different capabilities. Kimi K2.5 has a `thinking` toggle. OpenAI has separate full/mini models. Claude has neither. Baking any model's specific features into router logic creates lock-in.

**Solution: `MODEL_PROFILES`** — A capability profile that tells the router how to interact with a given configuration. The router consults the profile; it never hardcodes model-specific behavior.

**Profile keys are arbitrary human-readable names, not model IDs.** A profile can mix models from different providers — e.g., Kimi for complex tasks and Gemini Flash Lite for simple tasks. All models within a profile must be accessible through the same provider client (in practice this means all models are on OpenRouter, which is the primary operating mode).

```python
# model_config.py

MODEL_PROFILES = {
    # ================================================================
    # HYBRID PROFILES (mix models from different providers via OpenRouter)
    # These are the primary operating profiles.
    # ================================================================

    # ---- Recommended: Kimi for reasoning, Gemini Flash for cheap tasks ----
    "kimi-complex-gemini-simple": {
        "complex_model": "moonshotai/kimi-k2.5",
        "simple_model": "google/gemini-2.5-flash-lite",
        "complex_params": {"extra_body": {"thinking": {"type": "enabled"}}},
        "simple_params": {},
        "supports_json_mode": True,
        "max_context": 1_000_000,
        "cost_per_1k": 0.0002,  # Blended estimate
    },
    # ---- Kimi thinking for complex, Kimi instant for simple ----
    "kimi-thinking-split": {
        "complex_model": "moonshotai/kimi-k2.5",
        "simple_model": "moonshotai/kimi-k2.5",
        "complex_params": {"extra_body": {"thinking": {"type": "enabled"}}},
        "simple_params": {"extra_body": {"thinking": {"type": "disabled"}}},
        "supports_json_mode": True,
        "max_context": 1_000_000,
        "cost_per_1k": 0.0003,
    },

    # ================================================================
    # SINGLE-PROVIDER PROFILES (all tasks use one provider's models)
    # Useful as baselines or for testing a new provider.
    # ================================================================

    # ---- Kimi K2.5: Single model, thinking toggle ----
    "moonshotai/kimi-k2.5": {
        "complex_model": "moonshotai/kimi-k2.5",
        "simple_model": "moonshotai/kimi-k2.5",
        "complex_params": {"extra_body": {"thinking": {"type": "enabled"}}},
        "simple_params": {"extra_body": {"thinking": {"type": "disabled"}}},
        "supports_json_mode": True,
        "max_context": 1_000_000,
        "cost_per_1k": 0.0003,
    },
    # ---- Gemini: Dual model (pro + flash) ----
    "google/gemini-2.5": {
        "complex_model": "google/gemini-2.5-pro",
        "simple_model": "google/gemini-2.5-flash-lite",
        "complex_params": {},
        "simple_params": {},
        "supports_json_mode": True,
        "max_context": 1_050_000,
        "cost_per_1k": 0.0001,
    },
    # ---- Claude: Dual model (sonnet + haiku) ----
    "anthropic/claude-3.5": {
        "complex_model": "anthropic/claude-3.5-sonnet",
        "simple_model": "anthropic/claude-3.5-haiku",
        "complex_params": {},
        "simple_params": {},
        "supports_json_mode": True,
        "max_context": 200_000,
        "cost_per_1k": 0.003,
    },

    # ================================================================
    # FALLBACK PROFILE (OpenAI direct — safety net when OpenRouter is down)
    # This profile is used automatically on provider failure.
    # Not an operating mode — just the safety net.
    # ================================================================

    "openai/gpt-4.1": {
        "complex_model": "gpt-4.1-2025-04-14",
        "simple_model": "gpt-4.1-mini-2025-04-14",
        "complex_params": {},
        "simple_params": {},
        "supports_json_mode": True,
        "max_context": 1_000_000,
        "cost_per_1k": 0.002,
    },
}

# Default profile for unknown models — vanilla behavior, no special params
DEFAULT_PROFILE = {
    "complex_model": None,  # Use OPENROUTER_CHAT_MODEL as-is
    "simple_model": None,   # Use OPENROUTER_CHAT_MODEL as-is
    "complex_params": {},
    "simple_params": {},
    "supports_json_mode": True,
    "max_context": 128_000,
    "cost_per_1k": 0.002,
}
```

**Router logic:**

```python
profile = MODEL_PROFILES.get(configured_model, DEFAULT_PROFILE)
is_complex = task in COMPLEX_TASKS

model = profile["complex_model"] if is_complex else profile["simple_model"]
model = model or configured_model  # Fallback if profile field is None
params = profile["complex_params"] if is_complex else profile["simple_params"]

api_params["model"] = model
api_params.update(params)
```

**This handles all patterns:**

| Profile | complex_model | simple_model | complex_params | simple_params |
|---------|--------------|-------------|----------------|---------------|
| kimi-complex-gemini-simple | kimi-k2.5 | gemini-2.5-flash-lite | thinking=enabled | (none) |
| kimi-thinking-split | kimi-k2.5 | kimi-k2.5 | thinking=enabled | thinking=disabled |
| moonshotai/kimi-k2.5 | kimi-k2.5 | kimi-k2.5 | thinking=enabled | thinking=disabled |
| google/gemini-2.5 | gemini-2.5-pro | gemini-2.5-flash-lite | (none) | (none) |
| anthropic/claude-3.5 | claude-3.5-sonnet | claude-3.5-haiku | (none) | (none) |
| openai/gpt-4.1 (fallback) | gpt-4.1 | gpt-4.1-mini | (none) | (none) |
| (unknown model) | (configured) | (configured) | (none) | (none) |

**Config workflow:**

```python
# Use Kimi for reasoning + Gemini Flash for cheap tasks:
OPENROUTER_CHAT_MODEL = "kimi-complex-gemini-simple"

# Switch to pure Gemini for testing:
OPENROUTER_CHAT_MODEL = "google/gemini-2.5"

# Switch to pure Claude:
OPENROUTER_CHAT_MODEL = "anthropic/claude-3.5"

# Try a brand new model with no profile:
OPENROUTER_CHAT_MODEL = "new-provider/new-model"
# DEFAULT_PROFILE applies. No crash, no special params.
# Add a profile later to optimize.

# Create your own hybrid:
MODEL_PROFILES["my-custom-mix"] = {
    "complex_model": "anthropic/claude-3.5-sonnet",
    "simple_model": "google/gemini-2.5-flash-lite",
    "complex_params": {},
    "simple_params": {},
    "supports_json_mode": True,
    "max_context": 200_000,
    "cost_per_1k": 0.002,
}
OPENROUTER_CHAT_MODEL = "my-custom-mix"
```

**Three levels of control:**

1. **Global:** Change `OPENROUTER_CHAT_MODEL` — affects all tasks
2. **Per-task:** Add to `TASK_OVERRIDES` — affects one task, can point to a different profile
3. **Per-profile:** Edit or create a profile — define any mix of models and params

**Rename: `THINKING_ENABLED_TASKS` -> `COMPLEX_TASKS`**

The list classifies tasks by reasoning complexity, not by any model-specific feature. "Complex" means "needs deep reasoning" — how that's expressed depends on the model's profile:
- Kimi: `thinking: enabled`
- OpenAI: routes to gpt-4.1 (full) instead of gpt-4.1-mini
- Claude: routes to sonnet instead of haiku
- Unknown model: same model, no special params (still works, just not optimized)

**Deprecations (Phase 0):**

These `model_config.py` settings are replaced by `MODEL_PROFILES` and can be removed after migration:

| Deprecated | Replaced By |
|------------|-------------|
| `OPENROUTER_STRATEGY` | Profile determines strategy (single model with params vs dual model) |
| `OPENROUTER_FULL_MODEL` | `profile["complex_model"]` |
| `OPENROUTER_MINI_MODEL` | `profile["simple_model"]` |
| `THINKING_ENABLED_TASKS` | `COMPLEX_TASKS` (same list, renamed) |

### Provider Detection

Uses `LLM_PROVIDER` from `model_config.py` (via `_get_actual_provider()` in the factory). Does NOT depend on `MULTIPLAYER_MODE` — this aligns with the SP/MP unification roadmap.

**Primary operating mode:** `LLM_PROVIDER = "openrouter"` — All models accessed through OpenRouter. Profile determines which models are used for complex vs simple tasks. This is how the game is intended to run.

**Fallback safety net:** `LLM_PROVIDER = "openai"` or missing OpenRouter key — Falls back to direct OpenAI using `"openai/gpt-4.1"` profile (gpt-4.1 for complex, gpt-4.1-mini for simple). This is the existing upstream behavior and serves as the safety net when OpenRouter is unavailable, not a primary operating mode.

**Automatic fallback:** When a call fails on OpenRouter (503, rate limit, timeout), the router automatically retries using the `"openai/gpt-4.1"` fallback profile with a direct OpenAI client. No config change needed — happens transparently per-call.

Transparent to callers: `llm.call()` works identically regardless of provider.

---

## Implementation

### Phase 1: Router Facade (1-2 days)

**Create `utils/llm_router.py` (~250 lines):**

```python
"""
LLM Router - Unified, model-agnostic interface for all AI calls.
Thin facade over ai_client_factory infrastructure.
Uses MODEL_PROFILES for provider-agnostic model selection.
"""

import json
from threading import Lock
from typing import Dict, List, Any, Optional, Union

from utils.enhanced_logger import debug, info, warning, error
from utils.ai_client_factory import (
    create_chat_client,
    handle_provider_error,
    get_fallback_notification,
)


# ============================================================================
# Exceptions
# ============================================================================

class GameLLMError(Exception):
    """AI provider cannot fulfill requests. Game cannot continue."""
    pass

class LLMJSONError(Exception):
    """LLM returned content that could not be parsed as JSON."""
    pass


# ============================================================================
# Cost Tracking (Thread-Safe)
# ============================================================================

_usage_lock = Lock()
_usage_stats = {
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "calls": 0,
    "errors": 0,
    "fallbacks": 0,
    "by_model": {},
    "by_task": {},
}


# ============================================================================
# Router Class
# ============================================================================

class LLMRouter:
    """
    Unified, model-agnostic LLM call interface.
    
    Uses MODEL_PROFILES from model_config.py to adapt to any model's
    capabilities without hardcoding provider-specific behavior.
    
    Delegates to ai_client_factory for client creation.
    Adds: profile-based routing, cost tracking, JSON retry, error handling.
    """
    
    MAX_JSON_RETRIES = 3
    
    def _get_profile_and_model(self, task: str):
        """
        Resolve the active profile and select the correct model for a task.
        
        Returns:
            (profile, model, params, fallback_profile, fallback_model, temperature)
        """
        from model_config import (
            MODEL_PROFILES, DEFAULT_PROFILE, COMPLEX_TASKS,
            TASK_TEMPERATURES, TASK_OVERRIDES,
            OPENROUTER_CHAT_MODEL, LLM_PROVIDER,
        )
        from utils.ai_client_factory import _get_actual_provider
        
        _, is_openrouter = _get_actual_provider()
        is_complex = task in COMPLEX_TASKS
        
        # Determine active profile key
        if is_openrouter:
            profile_key = OPENROUTER_CHAT_MODEL
        else:
            profile_key = "openai/gpt-4.1"
        
        # Check for per-task override
        if task in TASK_OVERRIDES:
            override = TASK_OVERRIDES[task]
            if "profile" in override:
                profile_key = override["profile"]
        
        # Look up profile (fall back to DEFAULT_PROFILE for unknown models)
        profile = MODEL_PROFILES.get(profile_key, DEFAULT_PROFILE)
        
        # Select model based on task complexity
        if is_complex:
            model = profile["complex_model"] or profile_key
            params = dict(profile.get("complex_params", {}))
        else:
            model = profile["simple_model"] or profile_key
            params = dict(profile.get("simple_params", {}))
        
        # Per-task model override (overrides profile selection)
        if task in TASK_OVERRIDES and "model" in TASK_OVERRIDES[task]:
            model = TASK_OVERRIDES[task]["model"]
            params = {}  # Unknown model — don't apply profile params
        
        # Temperature: task-specific > profile default
        temp = TASK_TEMPERATURES.get(task, 0.7)
        
        # Fallback profile (always OpenAI)
        fallback_profile = MODEL_PROFILES.get("openai/gpt-4.1", DEFAULT_PROFILE)
        if is_complex:
            fallback_model = fallback_profile["complex_model"] or "gpt-4.1-2025-04-14"
        else:
            fallback_model = fallback_profile["simple_model"] or "gpt-4.1-mini-2025-04-14"
        
        return profile, model, params, fallback_profile, fallback_model, temp
    
    def call(
        self,
        task: str,
        messages: List[Dict[str, str]],
        json_output: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Make an LLM call with automatic routing, tracking, and error handling.
        
        Args:
            task: Task identifier (e.g., "dm_main", "combat_main")
            messages: Standard OpenAI message format
            json_output: If True, parse response as JSON with retry logic
            temperature: Override the task's default temperature
            max_tokens: Override max tokens
            **kwargs: Passed through to completions.create()
            
        Returns:
            str: Raw text response (when json_output=False)
            Dict: Parsed JSON dict (when json_output=True)
            
        Raises:
            GameLLMError: Quota/billing error (game must stop)
            LLMJSONError: JSON parsing failed after retries
        """
        # 1. Resolve profile and model for this task
        profile, model, params, fb_profile, fb_model, default_temp = \
            self._get_profile_and_model(task)
        
        # 2. Create provider-appropriate client
        client = create_chat_client(use_fallback=False)
        
        # 3. Build API parameters
        api_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature if temperature is not None else default_temp,
        }
        
        if max_tokens is not None:
            api_params["max_tokens"] = max_tokens
        
        # Apply model-specific parameters from profile
        if params:
            api_params.update(params)
        
        if json_output:
            api_params["response_format"] = {"type": "json_object"}
        
        # Merge caller kwargs (last, so they can override anything)
        api_params.update(kwargs)
        
        # 4. Execute with error handling
        last_error = None
        used_fallback = False
        
        for attempt in range(self.MAX_JSON_RETRIES if json_output else 1):
            try:
                response = client.chat.completions.create(**api_params)
                content = response.choices[0].message.content
                
                # Track usage (cost from profile)
                cost_per_1k = profile.get("cost_per_1k", 0.002)
                self._track_usage(response, task, api_params["model"], cost_per_1k)
                
                if json_output:
                    return self._parse_json(content, task)
                return content
                
            except Exception as e:
                last_error = e
                
                # Classify the error
                if self._is_quota_error(e):
                    self._track_error(task)
                    raise GameLLMError(
                        f"AI provider quota/billing error for task '{task}': {e}\n"
                        f"Model: {api_params['model']}\n"
                        f"The game cannot continue without AI access.\n\n"
                        f"Options:\n"
                        f"1. Check your provider account balance\n"
                        f"2. Set LLM_PROVIDER = 'openai' in model_config.py\n"
                        f"3. Change models in model_config.py TASK_OVERRIDES\n"
                        f"4. Switch OPENROUTER_CHAT_MODEL to a different profile"
                    )
                
                if self._is_retryable(e) and not used_fallback:
                    # Switch to fallback model using its profile
                    used_fallback = True
                    self._track_fallback(task)
                    
                    handle_provider_error(e, context=task)
                    
                    # Apply fallback profile — model + params change together
                    api_params["model"] = fb_model
                    # Remove primary model's params, apply fallback's
                    api_params.pop("extra_body", None)
                    fb_params = fb_profile.get("complex_params", {}) \
                        if task in self._get_complex_tasks() \
                        else fb_profile.get("simple_params", {})
                    if fb_params:
                        api_params.update(fb_params)
                    
                    client = create_chat_client(use_fallback=True)
                    profile = fb_profile  # Update cost tracking
                    
                    info(f"Fallback to {fb_model} for task {task}: {e}",
                         category="ai_provider")
                    continue
                
                if json_output and isinstance(e, json.JSONDecodeError) \
                        and attempt < self.MAX_JSON_RETRIES - 1:
                    # JSON parse failed — retry (the LLM call succeeded)
                    warning(f"JSON parse failed for {task} (attempt {attempt + 1}): {e}",
                            category="ai_provider")
                    continue
                
                # Not retryable, not JSON retry — raise
                self._track_error(task)
                raise
        
        # Exhausted retries
        self._track_error(task)
        if json_output and last_error:
            raise LLMJSONError(
                f"Failed to get valid JSON for task '{task}' after "
                f"{self.MAX_JSON_RETRIES} attempts: {last_error}"
            )
        raise last_error
    
    @staticmethod
    def _get_complex_tasks():
        """Import COMPLEX_TASKS at call time to avoid circular imports."""
        try:
            from model_config import COMPLEX_TASKS
            return COMPLEX_TASKS
        except ImportError:
            return []
    
    # ------------------------------------------------------------------
    # JSON Parsing
    # ------------------------------------------------------------------
    
    def _parse_json(self, content: str, task: str) -> Dict[str, Any]:
        """Parse LLM response as JSON. Raises json.JSONDecodeError on failure."""
        if not content or not content.strip():
            raise json.JSONDecodeError("Empty response", content or "", 0)
        
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        
        return json.loads(text)
    
    # ------------------------------------------------------------------
    # Error Classification
    # ------------------------------------------------------------------
    
    @staticmethod
    def _is_quota_error(e: Exception) -> bool:
        msg = str(e).lower()
        return any(term in msg for term in [
            'quota', 'billing', 'payment', 'insufficient_quota',
            'exceeded your current usage', 'account balance'
        ])
    
    @staticmethod
    def _is_retryable(e: Exception) -> bool:
        msg = str(e).lower()
        return any(term in msg for term in [
            'rate limit', 'timeout', 'connection', '503', '502', '504',
            'overloaded', 'unavailable', 'internal server error', '429',
            'bad gateway'
        ])
    
    # ------------------------------------------------------------------
    # Usage Tracking (Thread-Safe)
    # ------------------------------------------------------------------
    
    @staticmethod
    def _track_usage(response, task: str, model: str, cost_per_1k: float = 0.002):
        usage = getattr(response, 'usage', None)
        if not usage:
            return
        
        total = getattr(usage, 'total_tokens', 0)
        cost = cost_per_1k * (total / 1000)
        
        with _usage_lock:
            _usage_stats["total_tokens"] += total
            _usage_stats["total_cost_usd"] += cost
            _usage_stats["calls"] += 1
            _usage_stats["by_model"][model] = _usage_stats["by_model"].get(model, 0) + total
            _usage_stats["by_task"][task] = _usage_stats["by_task"].get(task, 0) + total
        
        debug(f"LLM: {task} | {model} | {total} tokens | ${cost:.4f}",
              category="ai_provider")
    
    @staticmethod
    def _track_error(task: str):
        with _usage_lock:
            _usage_stats["errors"] += 1
    
    @staticmethod
    def _track_fallback(task: str):
        with _usage_lock:
            _usage_stats["fallbacks"] += 1
    
    # ------------------------------------------------------------------
    # Public Stats API
    # ------------------------------------------------------------------
    
    @staticmethod
    def get_usage_stats() -> Dict[str, Any]:
        """Get current session usage statistics (thread-safe copy)."""
        with _usage_lock:
            return {
                "total_tokens": _usage_stats["total_tokens"],
                "total_cost_usd": round(_usage_stats["total_cost_usd"], 4),
                "total_calls": _usage_stats["calls"],
                "total_errors": _usage_stats["errors"],
                "total_fallbacks": _usage_stats["fallbacks"],
                "by_model": dict(_usage_stats["by_model"]),
                "by_task": dict(_usage_stats["by_task"]),
            }
    
    @staticmethod
    def reset_usage_stats():
        """Reset statistics. Call at game/session start."""
        with _usage_lock:
            _usage_stats.update({
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "calls": 0,
                "errors": 0,
                "fallbacks": 0,
                "by_model": {},
                "by_task": {},
            })
        debug("LLM usage stats reset", category="ai_provider")


# Module-level singleton
llm = LLMRouter()
```

**Update `model_config.py`:** Add `MODEL_PROFILES`, `DEFAULT_PROFILE`, and rename `THINKING_ENABLED_TASKS` to `COMPLEX_TASKS`. See Model Agnosticism section above for the full config. Deprecate `OPENROUTER_STRATEGY`, `OPENROUTER_FULL_MODEL`, `OPENROUTER_MINI_MODEL` (keep for backward compatibility, mark as deprecated in comments).

**No new dependencies.** Uses `json.loads()` for structured output, not Pydantic.

---

### Phase 2: File Migration (4-5 days)

#### Migration Pattern

```python
# BEFORE (unmigrated file - 29 files use this pattern):
from openai import OpenAI
from config import OPENAI_API_KEY
from model_config import DM_MAIN_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)
response = client.chat.completions.create(
    model=DM_MAIN_MODEL,
    temperature=0.7,
    messages=prompt
)
result = response.choices[0].message.content

# BEFORE (partially migrated - 8 files use this pattern):
from utils.ai_client_factory import create_chat_client, get_chat_model_name
from model_config import DM_MAIN_MODEL

client = create_chat_client()
response = client.chat.completions.create(
    model=DM_MAIN_MODEL,      # Still hardcoded, bypasses 3-tier routing
    temperature=0.7,
    messages=prompt
)
result = response.choices[0].message.content

# AFTER (target state):
from utils.llm_router import llm

result = llm.call(task="dm_main", messages=prompt)
# Model, temperature, provider, error handling — all automatic
```

#### Priority Order

**Tier 1: Core Game Loop (Day 1-2) — Highest traffic, highest risk**

| File | Calls | Current State | Notes |
|------|-------|---------------|-------|
| `main.py` | 8 | Partial (factory client, hardcoded models) | Line 1727: raw `OpenAI()` in `generate_module_summary()` — standard chat.completions.create using `DM_SUMMARIZATION_MODEL`, migrate as `task="summaries"` |
| `core/managers/combat_manager.py` | 9 | Partial (factory client, 6 hardcoded model constants) | Highest call count |
| `core/ai/action_handler.py` | 6 | Partial (3 inline factory imports, manual fallback) | Complex fallback chains |

**Tier 2: Already Factory-Migrated (Day 2-3) — Lowest risk, just simplify**

| File | Calls | Current State | Notes |
|------|-------|---------------|-------|
| `core/ai/adv_summary.py` | 2 | Full (`get_model_config`) | Simplify to `llm.call()` |
| `core/ai/cumulative_summary.py` | 2 | Full (`get_model_config`) | Simplify to `llm.call()` |
| `updates/plot_update.py` | 1 | Full (`get_model_config`) | Simplify to `llm.call()` |
| `updates/update_encounter.py` | 1 | Full (`get_model_config`) | Simplify to `llm.call()` |
| `updates/update_character_info.py` | 1 | Partial (factory client, manual fallback) | |
| `web/web_interface.py` | 2 chat | Partial (1 uses `get_model_config`) | Skip image/TTS calls |
| `core/ai/combat_compression_engine.py` | 1 | Partial (factory client) | |
| `core/ai/incremental_compression.py` | 1 | Partial (factory client) | |
| `utils/startup_wizard.py` | 2 | Partial (factory client) | |

**Tier 3: Generators (Day 3-4) — Medium risk, consistent patterns**

| File | Calls | Notes |
|------|-------|-------|
| `core/generators/module_builder.py` | 3 | 3 separate `OpenAI()` instantiations |
| `core/generators/area_generator.py` | 3 | Module-level client |
| `core/generators/location_generator.py` | 2 | Module-level client |
| `core/generators/plot_generator.py` | 2 | Module-level client |
| `core/generators/module_stitcher.py` | 2 | `__init__` self.client |
| `core/generators/npc_builder.py` | 1 | |
| `core/generators/monster_builder.py` | 1 | |
| `core/generators/location_summarizer.py` | 1 | `__init__` self.client |
| `core/generators/module_generator.py` | 1 | |

**Tier 4: Utilities & Validation (Day 4-5) — Low risk, simple patterns**

| File | Calls | Notes |
|------|-------|-------|
| `core/validation/character_validator.py` | 4 | All same model + temp 0.1 |
| `core/validation/character_validator_backup.py` | 4 | Identical to above |
| `core/validation/character_effects_validator.py` | 1 | |
| `core/validation/npc_codex_generator.py` | 1 | |
| `core/managers/level_up_manager.py` | 2 | |
| `core/managers/campaign_manager.py` | 2 | |
| `core/managers/storage_processor.py` | 1 | |
| `core/managers/initiative_tracker_ai.py` | 1 | |
| `core/ai/transition_validator.py` | 1 | Listed as "partially migrated" in AGENTS.md but actually unmigrated |
| `utils/action_predictor.py` | 1 | |
| `utils/level_up.py` | 1 | |
| `utils/prompt_sanitizer.py` | 1 | |
| `utils/quest_player_formatter.py` | 1 | |
| `utils/npc_reconciler.py` | 1 | |
| `utils/npc_name_canonicalizer.py` | 1 | |
| `utils/bestiary_updater.py` | 1 | |
| `utils/reconcile_location_state.py` | 1 | |
| `utils/compression/location_compressor.py` | 1 | |
| `utils/compression/ai_narrative_compressor_agentic.py` | 1 | |
| `updates/update_character_effects.py` | 1 | |

**Excluded from migration:**
- `core/toolkit/npc_generator.py` — Creates `OpenAI()` in `__init__` but uses it exclusively for `images.generate()` (DALL-E) and `models.list()` (account validation). Zero `chat.completions.create` calls. No subclasses. Image-only service — belongs in Phase 2 image/TTS scope.
- `core/toolkit/monster_generator.py` — Identical to above. Image-only service.

#### Task ID Assignment

Each call site needs a `task` parameter. Use the existing `model_config.py` constant as the guide:

| Original Model Constant | Task ID | Complex? | Effect |
|--------------------------|---------|----------|--------|
| `DM_MAIN_MODEL` | `dm_main` | Yes | Profile's complex_model + complex_params |
| `DM_VALIDATION_MODEL` | `dm_validation` | Yes | Profile's complex_model + complex_params |
| `COMBAT_MAIN_MODEL` | `combat_main` | Yes | Profile's complex_model + complex_params |
| `COMBAT_DIALOGUE_SUMMARY_MODEL` | `combat_dialogue_summary` | No | Profile's simple_model + simple_params |
| `DM_MINI_MODEL` | `dm_mini` | No | Profile's simple_model + simple_params |
| `DM_FULL_MODEL` | `dm_full` | Yes | Profile's complex_model + complex_params |
| `DM_SUMMARIZATION_MODEL` | `summaries` | No | Profile's simple_model + simple_params |
| `ADVENTURE_SUMMARY_MODEL` | `adventure_summary` | No | Profile's simple_model + simple_params |
| `PLOT_UPDATE_MODEL` | `plot_update` | No | Profile's simple_model + simple_params |
| `PLAYER_INFO_UPDATE_MODEL` | `player_info_update` | No | Profile's simple_model + simple_params |
| `NPC_INFO_UPDATE_MODEL` | `npc_info_update` | No | Profile's simple_model + simple_params |
| `ENCOUNTER_UPDATE_MODEL` | `encounter_update` | No | Profile's simple_model + simple_params |
| `CHARACTER_VALIDATOR_MODEL` | `character_validator` | Yes | Profile's complex_model + complex_params |
| `NPC_BUILDER_MODEL` | `npc_builder` | Yes | Profile's complex_model + complex_params |
| `MONSTER_BUILDER_MODEL` | `monster_builder` | Yes | Profile's complex_model + complex_params |
| `LEVEL_UP_MODEL` | `level_up` | Yes | Profile's complex_model + complex_params |
| `TRANSITION_VALIDATOR_MODEL` | `transition_validation` | No | Profile's simple_model + simple_params |
| `ACTION_PREDICTION_MODEL` | `action_prediction` | Yes | Profile's complex_model + complex_params |
| `NARRATIVE_COMPRESSION_MODEL` | `narrative_compression` | No | Profile's simple_model + simple_params |
| `LOCATION_COMPRESSION_MODEL` | `location_compression` | Yes | Profile's complex_model + complex_params |

---

### Phase 3: Cleanup & Polish (1-2 days)

#### 1. Remove Dead Code from `ai_client_factory.py`

These functions have zero consumers — delete immediately:

- `get_model_for_task()` (line 520) — never imported
- `is_thinking_enabled()` (line 481) — never imported
- `get_task_complexity()` (line 502) — never imported

These functions will have zero consumers after full migration — delete them:

- `get_chat_model_name()` — replaced by profile-based routing via router
- `get_model_display_name()` — only used by `get_chat_model_name()` consumers
- `get_model_config()` — replaced by `MODEL_PROFILES` in router's `_get_profile_and_model()`. Router uses `create_chat_client()` directly for client creation and consults profiles for model/params.

Keep:

- `create_chat_client()` — used by router for client creation
- `_get_actual_provider()` — used by router for provider detection
- `handle_provider_error()` — used by router
- `get_fallback_notification()` — used by router and web UI
- `reset_fallback_status()` — used at game start
- `get_provider_status()` — diagnostics
- `create_image_client()` — Phase 2 (image/TTS)
- `create_tts_client()` — Phase 2 (image/TTS)

#### 1b. Remove Deprecated Config from `model_config.py`

After full migration, these are replaced by `MODEL_PROFILES`:

- `OPENROUTER_STRATEGY` — replaced by profile's complex/simple model fields
- `OPENROUTER_FULL_MODEL` — replaced by `profile["complex_model"]`
- `OPENROUTER_MINI_MODEL` — replaced by `profile["simple_model"]`
- `THINKING_ENABLED_TASKS` alias — keep only `COMPLEX_TASKS`

#### 2. Remove Legacy Imports from Migrated Files

After migration, each file should have only:
```python
from utils.llm_router import llm
```

Remove from each migrated file:
- `from openai import OpenAI`
- `from config import OPENAI_API_KEY`
- `from model_config import DM_MAIN_MODEL` (and all other model constants)
- `from utils.ai_client_factory import create_chat_client, get_chat_model_name, ...`
- Module-level `client = OpenAI(...)` or `client = create_chat_client()`

Exception: Files that use model constants for non-LLM purposes (logging, display) may keep those imports.

#### 3. Add Usage Reporting

Add `/usage` command to game interface:

```python
# In main.py or web_interface.py
from utils.llm_router import llm

def handle_usage_command():
    stats = llm.get_usage_stats()
    return (
        f"LLM Usage This Session:\n"
        f"  Calls: {stats['total_calls']}\n"
        f"  Tokens: {stats['total_tokens']:,}\n"
        f"  Cost: ${stats['total_cost_usd']:.4f}\n"
        f"  Errors: {stats['total_errors']}\n"
        f"  Fallbacks: {stats['total_fallbacks']}\n"
        f"\nBy Task:\n"
        + "\n".join(f"  {t}: {n:,} tokens" for t, n in sorted(
            stats['by_task'].items(), key=lambda x: -x[1]))
    )
```

#### 4. Update Documentation

- Update AGENTS.md "OpenRouter Integration" section to reflect router pattern
- Remove references to `get_chat_model_name()` pattern
- Add migration pattern documentation

---

## Error Handling

### Error Classification

| Error Type | Action | Example |
|------------|--------|---------|
| **Quota/Billing** | Hard stop — raise `GameLLMError` | "exceeded your current usage limit" |
| **Transient** | Retry with fallback model | 429 rate limit, 503, timeout, connection error |
| **JSON Parse** | Retry LLM call (up to 3 attempts) | Invalid JSON in structured output |
| **Other** | Re-raise to caller | Unexpected API errors |

### Hard Stop Display

```
[CRITICAL ERROR]
AI provider quota/billing error for task 'dm_main': ...

The game cannot continue without AI access.

Options:
1. Check your OpenRouter account balance
2. Set LLM_PROVIDER = "openai" in model_config.py
3. Change models in model_config.py TASK_OVERRIDES
```

---

## Testing Strategy

### Unit Tests (No API calls)

```python
# scripts/test_llm_router.py

def test_error_classification():
    """Verify error types are correctly classified."""
    router = LLMRouter()
    assert router._is_quota_error(Exception("exceeded your current usage limit"))
    assert router._is_quota_error(Exception("insufficient_quota"))
    assert not router._is_quota_error(Exception("connection timeout"))
    
    assert router._is_retryable(Exception("rate limit exceeded"))
    assert router._is_retryable(Exception("503 Service Unavailable"))
    assert not router._is_retryable(Exception("invalid api key"))

def test_json_parsing():
    """Verify JSON extraction handles edge cases."""
    router = LLMRouter()
    assert router._parse_json('{"key": "value"}', "test") == {"key": "value"}
    assert router._parse_json('```json\n{"key": "value"}\n```', "test") == {"key": "value"}

def test_usage_tracking():
    """Verify thread-safe usage stats."""
    LLMRouter.reset_usage_stats()
    stats = LLMRouter.get_usage_stats()
    assert stats["total_calls"] == 0
    assert stats["total_tokens"] == 0

def test_complex_tasks_coverage():
    """Verify all complex tasks are recognized by the router."""
    from model_config import COMPLEX_TASKS, TASK_TEMPERATURES
    for task in COMPLEX_TASKS:
        assert task in TASK_TEMPERATURES, f"Missing temperature for {task}"

def test_profile_resolution():
    """Verify profile lookup works for known and unknown models."""
    from model_config import MODEL_PROFILES, DEFAULT_PROFILE
    # Known model returns its profile
    assert "moonshotai/kimi-k2.5" in MODEL_PROFILES
    kimi = MODEL_PROFILES["moonshotai/kimi-k2.5"]
    assert kimi["complex_model"] == "moonshotai/kimi-k2.5"
    assert "thinking" in str(kimi["complex_params"])
    
    # Unknown model returns DEFAULT_PROFILE
    assert MODEL_PROFILES.get("unknown/model", DEFAULT_PROFILE) == DEFAULT_PROFILE
    assert DEFAULT_PROFILE["complex_params"] == {}

def test_dual_model_profile():
    """Verify OpenAI profile routes complex/simple to different models."""
    from model_config import MODEL_PROFILES
    openai = MODEL_PROFILES["openai/gpt-4.1"]
    assert openai["complex_model"] != openai["simple_model"]
    assert "4.1-2025" in openai["complex_model"]
    assert "mini" in openai["simple_model"]
```

### Manual Testing Checklist

- [ ] `llm.call(task="dm_main", messages=[...])` returns narration text
- [ ] `llm.call(task="dm_main", messages=[...], json_output=True)` returns parsed dict
- [ ] Fallback triggers when OpenRouter returns 503
- [ ] `GameLLMError` raised on quota error
- [ ] `llm.get_usage_stats()` shows correct token counts after calls
- [ ] Works with `LLM_PROVIDER = "openai"` (uses `openai/gpt-4.1` profile)
- [ ] Works with `LLM_PROVIDER = "openrouter"` (uses configured profile)
- [ ] Temperature override works: `llm.call(..., temperature=0.1)`
- [ ] Profile swap: change `OPENROUTER_CHAT_MODEL`, restart, verify new model used
- [ ] Unknown model: set `OPENROUTER_CHAT_MODEL` to nonexistent profile, verify DEFAULT_PROFILE applies
- [ ] `TASK_OVERRIDES` with `"profile"` key correctly redirects a single task

---

## Migration Checklist

### Phase 0: Config & Factory Prep (Prerequisite)
- [ ] Add `MODEL_PROFILES`, `DEFAULT_PROFILE` to `model_config.py`
- [ ] Rename `THINKING_ENABLED_TASKS` to `COMPLEX_TASKS` (keep alias for backward compat)
- [ ] Mark `OPENROUTER_STRATEGY`, `OPENROUTER_FULL_MODEL`, `OPENROUTER_MINI_MODEL` as deprecated in comments
- [ ] Normalize `extra_body` shape in `ai_client_factory.py` `get_model_config()` (short-term fix until router takes over param generation)
- [ ] Verify 5 existing consumer files still compile after changes

### Phase 1: Router Facade
- [ ] Create `utils/llm_router.py` (~250 lines)
- [ ] Profile-based routing via `_get_profile_and_model()`
- [ ] Write unit tests (error classification, JSON parsing, stats, profile resolution)
- [ ] Manual test: switch `OPENROUTER_CHAT_MODEL` between profiles, verify correct model/params selected
- [ ] Manual test with both OpenAI and OpenRouter providers
- [ ] Verify cost tracking uses profile's `cost_per_1k`

### Phase 2: File Migration (42 chat files -> `llm.call()`)
- [ ] Tier 1: `main.py` (8), `combat_manager.py` (9), `action_handler.py` (6)
- [ ] Tier 2: 9 already-factory-migrated files (simplify to `llm.call()`)
- [ ] Tier 3: 9 generator files (16 calls total)
- [ ] Tier 4: 18 utility/validation/update files (23 calls total)
- [ ] Add `llm.reset_usage_stats()` to `main.py` startup (terminal mode)
- [ ] Add `llm.reset_usage_stats()` to `web_interface.py` server start (web mode)
- [ ] Verify each file compiles (`python -m py_compile`)
- [ ] In-game smoke test after each tier

### Phase 3: Cleanup
- [ ] Delete dead code from `ai_client_factory.py` (3+ functions — see cleanup list)
- [ ] Remove `OPENROUTER_STRATEGY`, `OPENROUTER_FULL_MODEL`, `OPENROUTER_MINI_MODEL` from `model_config.py`
- [ ] Remove `THINKING_ENABLED_TASKS` alias (keep only `COMPLEX_TASKS`)
- [ ] Remove legacy imports from migrated files
- [ ] Add `/usage` command
- [ ] Update AGENTS.md
- [ ] Final in-game test (full session)

---

## Future Considerations

### Per-Task Model Experimentation

With `MODEL_PROFILES` in place, testing different models for different tasks requires no code changes:

**Redirect a single task to a different profile:**
```python
TASK_OVERRIDES = {
    "combat_main": {"profile": "google/gemini-2.5"},  # Use Gemini for combat only
}
```

**Redirect a single task to a specific model (bypass profile):**
```python
TASK_OVERRIDES = {
    "encounter_update": {"model": "google/gemini-2.5-flash-lite"},  # Cheap model for JSON
}
```

**Add a new model to test:**
```python
MODEL_PROFILES["meta/llama-4-maverick"] = {
    "complex_model": "meta/llama-4-maverick",
    "simple_model": "meta/llama-4-maverick",
    "complex_params": {},
    "simple_params": {},
    "supports_json_mode": True,
    "max_context": 1_000_000,
    "cost_per_1k": 0.0001,
}
OPENROUTER_CHAT_MODEL = "meta/llama-4-maverick"  # Switch globally
```

No code changes in any of these scenarios. No router modifications. No factory updates.

### Async Support (Deferred)

Not needed yet. Flask + SocketIO uses synchronous request handling. If the web server migrates to async (FastAPI, etc.), add `call_async()` at that time.

### Response Caching (Deferred)

Some calls are nearly deterministic (validation, schema extraction). Caching could save tokens. Evaluate after usage data from cost tracking reveals which tasks consume the most.

### Additional OpenAI-Compatible Providers (Deferred)

The factory's `create_chat_client()` already works by setting `base_url` + API key on the standard OpenAI Python SDK. Adding support for other OpenAI-compatible providers (local Ollama, Azure OpenAI, Together.ai, etc.) would mean:

1. Add a new `LLM_PROVIDER` option (e.g., `"ollama"`, `"azure"`)
2. Configure its `base_url` and API key in `config.py`
3. Add a `MODEL_PROFILES` entry for whatever models it serves
4. No router changes needed — it already uses profiles, not provider-specific logic

OpenAI-direct is already in place as the fallback and could become a first-class provider option (alongside OpenRouter) with minimal changes to `_get_actual_provider()`.

### API Timeout Protection & Escalating User Feedback (Router-Level)

**Context:** On 2026-02-09, combat validation hung indefinitely waiting for an OpenAI API response. The SDK default timeout is 600s (10 minutes). No timeout is set on any of the 85 `client.chat.completions.create()` call sites or on any `OpenAI()` constructor in the codebase. The user saw a static "Validating combat actions..." placeholder with no escalation or timeout recovery.

**Interim fix (pre-router):** A combat-specific timeout + escalating status timer will be applied directly to `combat_manager.py` for the current OpenAI-based TT build. See "Combat-Specific Timeout Fix" section below.

**Router-level fix (this plan):** When the router centralizes all 85 call sites behind `llm.call()`, timeout protection and user feedback become automatic for every LLM call, not just combat.

#### Client-Level Timeout

Apply `httpx.Timeout` on the `OpenAI()` constructor in `ai_client_factory.py`. This gives one configuration point for all call sites:

```python
import httpx

# In create_chat_client():
client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=httpx.Timeout(API_TIMEOUT_SECONDS, connect=API_CONNECT_TIMEOUT_SECONDS),
)
```

**Configuration constants** (add to `model_config.py`):
```python
API_TIMEOUT_SECONDS = 120      # Total request timeout (read + write + pool)
API_CONNECT_TIMEOUT_SECONDS = 10  # TCP connection timeout only
```

**Rationale for 120s:**
- OpenAI SDK default is 600s (absurd for interactive gameplay)
- Combat validation prompts can be large (46K+ chars observed) and slow models need time
- 120s is generous enough for complex prompts over OpenRouter, short enough to not lose players
- On timeout: triggers existing `handle_provider_error()` fallback to OpenAI

#### Escalating Status Timer (StatusTimer Context Manager)

A context manager that runs a background thread, escalating the status message while a blocking API call runs. Uses the existing `status_manager.update_status()` pipeline -- no frontend changes needed.

```python
# In core/managers/status_manager.py or utils/status_timer.py

from contextlib import contextmanager
from threading import Thread, Event

DEFAULT_ESCALATION_SCHEDULE = [
    (0,  None),                                  # Keep caller's initial message
    (10, "Still processing, please wait..."),     # Reassurance
    (30, "Response taking longer than usual..."), # Honesty
    (60, "Waiting for AI provider ({elapsed}s)..."),  # Transparency with elapsed time
]

@contextmanager
def status_timer(initial_message, schedule=None, update_fn=None):
    """
    Escalate status messages while a blocking operation runs.
    
    Usage:
        status_manager.update_status("Validating combat actions...", is_processing=True)
        with status_timer("Validating combat actions...", update_fn=status_manager.update_status):
            result = client.chat.completions.create(...)
        # Timer auto-cancels on exit
    """
    ...
```

**Integration in router's `call()` method:**

```python
def call(self, task, messages, status_callback=None, **kwargs):
    # If caller provided a status callback, wrap the API call in a timer
    if status_callback:
        with status_timer(f"Processing {task}...", update_fn=status_callback):
            response = client.chat.completions.create(**api_params)
    else:
        response = client.chat.completions.create(**api_params)
```

This way combat_manager can pass `status_manager.update_status` as the callback, while non-interactive callers (generators, validators) skip the timer entirely.

#### Implementation Checklist (Router Phase)

- [ ] Add `API_TIMEOUT_SECONDS` and `API_CONNECT_TIMEOUT_SECONDS` to `model_config.py`
- [ ] Add `timeout=httpx.Timeout(...)` to both client constructors in `ai_client_factory.py`
- [ ] Create `StatusTimer` context manager
- [ ] Add optional `status_callback` parameter to `llm.call()`
- [ ] Update combat_manager migration (Phase 2 Tier 1) to pass status callback
- [ ] Test timeout triggers fallback correctly
- [ ] Test escalating messages appear in UI during slow responses

---

### Combat-Specific Timeout Fix (Pre-Router, Current Build)

**Target:** `core/managers/combat_manager.py` -- the two blocking API calls in the combat retry loop (generation ~3581, validation ~849).

**Scope:** Surgical fix for the active OpenAI-based TT build, to be superseded by the router-level solution.

**Changes:**
1. **`model_config.py`** -- Add `COMBAT_API_TIMEOUT_SECONDS = 120` constant
2. **`core/managers/combat_manager.py`** -- Add `timeout=COMBAT_API_TIMEOUT_SECONDS` to the two combat API calls + the initial scene validation call
3. **`core/managers/status_manager.py`** -- Add `StatusTimer` context manager (reusable, same code the router will use later)
4. **`core/managers/combat_manager.py`** -- Wrap blocking API calls in `status_timer()` using existing `status_manager.update_status` callback

**Escalation schedule for combat:**
```
0-10s:   (keep initial message, e.g., "Combat AI processing your action...")
10-30s:  "Still processing, please wait..."
30-60s:  "Response taking longer than usual..."
60-120s: "Waiting for AI provider ({elapsed}s)..."
120s:    httpx.TimeoutException -> caught by retry loop, next attempt
```

**On timeout in combat retry loop:**
- The `httpx.TimeoutException` is caught by the existing `except Exception as e` at line ~3766
- The retry loop increments attempt counter and tries again (up to `max_retries = 5`)
- If all retries timeout, the existing fail-open behavior applies (line ~3763: "Max retries exceeded, using last response")

**Merge path:** When the router migration reaches combat_manager.py (Phase 2 Tier 1), the `timeout=` parameter is removed from direct API calls (router handles it via client-level timeout), and the `status_timer()` wrapping moves to use `llm.call(status_callback=...)` instead.

### Latency Tracking (Deferred)

Add wall-clock timing per call to `_track_usage()`. Useful for identifying slow models or degraded provider performance. Simple addition when needed:

```python
import time
start = time.monotonic()
response = client.chat.completions.create(**api_params)
elapsed = time.monotonic() - start
# Add to stats: _usage_stats["latency_by_task"][task].append(elapsed)
```

### Combat Prompt Optimization for Multi-Model Routing (Deferred)

**Context:** Audit of `prompts/combat/combat_sim_prompt_multipc_compressed.txt` (2026-02-09) identified prompt architecture issues that are harmless on GPT-4.1 but will cause problems on cheaper/smaller OpenRouter models. These changes are deferred until the OpenAI-based TT build ships and the router is implemented.

**Prerequisite:** Prompt issues P1-P5, P7-P8 from the current GPT-4.1 build should be fixed first (see AGENTS.md "MultiPCCombatManager Bug Fixes" section for the audit report). The fixes below build on that foundation.

#### P10: Prompt Splitting Strategy for Multi-Model Routing

**Problem:** The combat prompt is monolithic (576 lines, ~3500 tokens). All directives are loaded as `conversation_history[0]` regardless of model. Creative models don't need `@PREROLLS`/`@ATTACK_RESOLUTION` math rules. Mechanical models don't need `@NARRATION_STYLE`/`@FLAVOR` sensory quotas.

**Solution:** Split the prompt template into directive groups that the router selects based on model capability:

| Group | Directives | Tokens | Required By |
|-------|-----------|--------|-------------|
| **Core** (always included) | `@ROLE`, `@SOURCE_OF_TRUTH`, `@OUTPUT_CONTRACT`, `@ROUTING_RULES`, `@ACTIONS`, `@ROUND_RULES`, `@RESPONSE_SCHEMA`, `@VALIDATORS`, `@CRITICAL_CONSTRAINTS`, `@INPUT_CHANNELS`, `@PRIORITY_ORDER`, `@PHASE_MODEL` (new), `@TEXT_FILTER` | ~1500 | ALL models |
| **Narration** (creative models) | `@NARRATION_STYLE`, `@FLAVOR`, `@NARRATION`, `@TURN_CONTROL_ENHANCEMENTS`, `@NAME_POLICY`, `@EDGE_CASES` | ~600 | Trinity, GPT-4.1, Claude Sonnet |
| **Mechanics** (mechanical models) | `@PREROLLS`, `@ATTACK_RESOLUTION`, `@SAVE_PAUSE`, `@DEATH_GATE`, `@COMBAT_ACTION_PROTOCOL`, `@PLAYER_DICE`, `@PLAYER_ACTION_RESOLUTION`, `@SPELL_EFFECTS_TRACKING`, `@ROUND_ADVANCEMENT` | ~800 | Flash Lite, GPT-4.1-mini, Claude Haiku |
| **Multi-PC** (MP-only) | `@SPLIT_PARTY_GUIDANCE`, `@HOLDING`, `@PHASE_MODEL` (new), multi-PC rules from `@ROUND_FLOW`/`@STOP_RULES` | ~400 | All models in MP mode |
| **Examples** (optional priming) | `@MICRO_EXAMPLES`, `@USER_PROMPT_TEMPLATE` | ~800 | Creative models only |

**Implementation approach:**

```python
# prompts/combat/ directory structure:
# combat_core.txt           -- Core directive group (~1500 tokens)
# combat_narration.txt      -- Narration directive group (~600 tokens)
# combat_mechanics.txt      -- Mechanics directive group (~800 tokens)
# combat_multipc.txt        -- Multi-PC directive group (~400 tokens)
# combat_examples.txt       -- Examples directive group (~800 tokens)

# In combat_manager.py prompt loading:
def _build_combat_prompt(is_multipc: bool, model_profile: dict) -> str:
    """Assemble combat prompt from directive groups based on model capability."""
    sections = [read_prompt("combat/combat_core.txt")]
    
    # Model capability determines which groups to include
    if model_profile.get("narration_capable", True):
        sections.append(read_prompt("combat/combat_narration.txt"))
    if model_profile.get("mechanics_capable", True):
        sections.append(read_prompt("combat/combat_mechanics.txt"))
    if is_multipc:
        sections.append(read_prompt("combat/combat_multipc.txt"))
    if model_profile.get("needs_examples", True):
        sections.append(read_prompt("combat/combat_examples.txt"))
    
    return "\n\n".join(sections)
```

**MODEL_PROFILES extension:**

```python
MODEL_PROFILES = {
    "kimi-complex-gemini-simple": {
        # ... existing fields ...
        "narration_capable": True,    # Complex model does narration
        "mechanics_capable": True,    # Complex model does mechanics
        "needs_examples": False,      # Kimi follows schema without examples
    },
    "google/gemini-2.5": {
        # ... existing fields ...
        "narration_capable": False,   # Flash Lite is JSON-focused
        "mechanics_capable": True,    # Flash Lite handles math well
        "needs_examples": True,       # Needs examples for format compliance
    },
}
```

**Token savings per model tier:**

| Model Tier | Current | After Split | Savings |
|-----------|---------|-------------|---------|
| GPT-4.1 (full prompt) | ~3500 | ~3500 | 0 (keep all) |
| Creative-only (Trinity) | ~3500 | ~2900 | ~600 (drop mechanics) |
| Mechanical-only (Flash Lite) | ~3500 | ~2300 | ~1200 (drop narration + examples) |
| Mini/budget | ~3500 | ~1500 | ~2000 (core only) |

**Migration path:** Start with the monolithic prompt (current). When the router is implemented and a second model is added, split the file. No code changes needed in the prompt itself -- just file splitting.

#### P5: Active PC Identity Redundancy Tiers

**Problem:** Active PC identity is communicated 7-8 times per turn. Full redundancy costs ~200-300 tokens. Creative models need reinforcement to maintain character consistency. Mechanical models only need the authoritative source.

**Solution:** Two tiers controlled by model profile:

| Tier | Sources Kept | Tokens | For Models |
|------|-------------|--------|------------|
| **Full** (current) | All 7-8 sources | ~300 | Creative models (Trinity, GPT-4.1, Sonnet) |
| **Minimal** | Live Tracker `[>]` + REQUIRED RESPONSE box only | ~80 | Mechanical models (Flash Lite, GPT-4.1-mini, Haiku) |

**Implementation:** In `combat_manager.py`, the `multi_pc_context` block (lines 3483-3503) becomes conditional:

```python
if multi_pc_manager:
    if model_profile.get("narration_capable", True):
        # Full context: phase state + party summary + PC override
        multi_pc_context = f"""=== COMBAT PHASE STATE ===
CURRENT_PHASE: {current_phase}
...
{multi_pc_manager.format_party_turn_summary()}
{multi_pc_manager.format_pc_context_for_prompt(active_pc)}"""
    else:
        # Minimal context: phase state only (tracker [>] provides identity)
        multi_pc_context = f"""=== COMBAT PHASE STATE ===
CURRENT_PHASE: {current_phase}
PC_PHASE_COMPLETE: {multi_pc_manager.pc_phase_complete}"""
```

**Prerequisite:** P10 (prompt splitting) should be implemented first so model capabilities are available at prompt assembly time.

#### P11: Plain-Text Alternative for `get_required_response_prompt()`

**Problem:** Box-drawing characters (`╔═╗║╠╣╚╝`) in the REQUIRED RESPONSE prompt work well with GPT-4.1 but may confuse smaller models. The characters are not in cp1252 but are safe because they only flow through API JSON, never stdout. However, some models may waste tokens parsing visual structure or fail to extract content from boxes.

**Solution:** Create a `get_required_response_prompt_simple()` method on the facade that uses `@`-directive style:

```python
def get_required_response_prompt_simple(self) -> str:
    """Plain-text version of required response prompt for non-GPT models."""
    if self._turns.pc_phase_complete:
        pending = self.get_remaining_enemies_for_round()
        pc_names = list(self._state.pc_states.keys())
        return f"""@REQUIRED_RESPONSE={{
  phase: "ENEMY_PHASE",
  pc_phase_complete: true,
  resolve_in_order: {pending},
  forbidden_actors: {pc_names},
  rules: [
    "Resolve ALL listed enemies/NPCs in order",
    "NEVER narrate actions for forbidden PCs",
    "Stop after last enemy acts",
    "Return JSON: plan, narration, combat_round, actions"
  ]
}}"""
    # ... PC_PHASE equivalent ...
```

**Selection in combat_manager.py:**

```python
if model_profile.get("prefers_structured_prompts", False):
    required_response = multi_pc_manager.get_required_response_prompt_simple()
else:
    required_response = multi_pc_manager.get_required_response_prompt()
```

**MODEL_PROFILES extension:**

```python
"google/gemini-2.5": {
    # ... existing fields ...
    "prefers_structured_prompts": True,  # Use @-directive style, not box art
},
```

#### P6/P12: Conditional Examples and Template

**Problem:** `@USER_PROMPT_TEMPLATE` (~400 tokens) and `@MICRO_EXAMPLES` (~400 tokens) serve as few-shot priming for GPT-4.1 but are wasted on models that follow schemas directly.

**Solution:** Move both to the `combat_examples.txt` directive group (see P10). Only loaded when `model_profile.get("needs_examples", True)` is set.

**No implementation changes needed beyond P10's file splitting.**

#### Implementation Checklist (Prompt Optimization)

All items below are deferred until after the router is implemented and a second model is tested:

- [ ] P10: Split `combat_sim_prompt_multipc_compressed.txt` into 5 directive group files
- [ ] P10: Add `narration_capable`, `mechanics_capable`, `needs_examples` fields to MODEL_PROFILES
- [ ] P10: Update combat_manager.py prompt loading to use `_build_combat_prompt()`
- [ ] P5: Add redundancy tier logic to `multi_pc_context` assembly in combat_manager.py
- [ ] P11: Create `get_required_response_prompt_simple()` on MultiPCCombatManager
- [ ] P11: Add `prefers_structured_prompts` field to MODEL_PROFILES
- [ ] P6/P12: Move `@USER_PROMPT_TEMPLATE` and `@MICRO_EXAMPLES` to `combat_examples.txt`
- [ ] Regression test: Full combat session on GPT-4.1 with split prompts (must produce identical behavior)
- [ ] A/B test: Compare combat quality on Flash Lite with full prompt vs minimal prompt

---

## Decisions Log

| Decision | Rationale |
|----------|-----------|
| **Thin facade over existing factory** | Factory has 536 lines of tested infrastructure. Router adds interface + tracking, doesn't reimplement provider logic. |
| **Task-based routing, not capability-based** | Existing `THINKING_ENABLED_TASKS` + `TASK_TEMPERATURES` maps 1:1 to call sites. Capability buckets (creative/mechanics/structured) are too coarse — combat is both narrative and mechanical. |
| **Model-agnostic via MODEL_PROFILES** | No model lock-in. Profiles define how to interact with each model (thinking toggle, dual models, etc.). Swapping models is a config-only change. Unknown models get DEFAULT_PROFILE (vanilla behavior). |
| **COMPLEX_TASKS replaces THINKING_ENABLED_TASKS** | Task complexity is model-agnostic. "Complex" means "needs deep reasoning" — the profile determines how to express that (Kimi: thinking=enabled, OpenAI: gpt-4.1 full, Claude: sonnet). |
| **Dual-model support in profiles** | Upstream uses gpt-4.1 + gpt-4.1-mini. Kimi uses thinking toggle. Both patterns are first-class in MODEL_PROFILES via complex_model/simple_model fields. |
| **`LLM_PROVIDER` not `MULTIPLAYER_MODE`** | Aligns with SP/MP unification roadmap. Provider selection is independent of multiplayer mode. |
| **`json.loads()` not Pydantic** | Codebase has zero Pydantic usage. Adding a dependency for structured output validation is premature. |
| **Thread-safe stats with `Lock`** | Flask + SocketIO is multi-threaded. Follows pattern from `pc_manager.py` (`_stats_lock`). |
| **No separate `llm_usage_tracker.py`** | Usage tracking is ~40 lines. Doesn't justify its own module. Lives inside the router. |
| **Hybrid profiles are first-class** | Profile keys are arbitrary names, not model IDs. `complex_model` and `simple_model` can point to different providers (e.g., Kimi + Gemini). All models in a profile must be reachable via the same client (OpenRouter). |
| **OpenRouter is the primary mode, OpenAI-direct is the safety net** | Game is designed to run on OpenRouter for model flexibility. OpenAI-direct exists for fallback when OpenRouter is unavailable, not as an equal operating mode. |
| **Toolkit files excluded from migration** | `npc_generator.py` and `monster_generator.py` use `images.generate()` only — zero chat completions. Belong in image/TTS Phase 2 scope, not router migration. |
| **Flat-rate cost tracking in Phase 1** | Directional visibility (is session $0.50 or $50?) is sufficient. Input/output token price split deferred until real usage data shows it matters. |
| **JSON retry kept in Phase 1** | LLM output is non-deterministic — retrying the same call may produce valid JSON when the first didn't. The retry makes a fresh API call each iteration, not a no-op replay. |
| **Fix factory `extra_body` before router** | Inconsistent shapes between TIER 1 and TASK_OVERRIDES paths would cause TypeError on OpenRouter. Must normalize before router can consume it. Blocker for Phase 1. |
| **Deferred until TT build ships** | Testers waiting for OpenAI-based Tabletop Mode fork. OpenRouter migration is a post-ship enhancement, not a blocker. |

---

## Session Start Prompt

**For implementation session:**

"Implement Phase 0 + Phase 1 of the LLM Router from /plans/version-2/openrouter_llm_router_architecture.md.

Phase 0 (config & factory prep):
- Add MODEL_PROFILES dict and DEFAULT_PROFILE to model_config.py (see Model Agnosticism section for exact profiles: hybrid kimi-complex-gemini-simple, kimi-thinking-split, plus single-provider baselines for kimi, gemini, claude, and openai/gpt-4.1 fallback)
- Rename THINKING_ENABLED_TASKS to COMPLEX_TASKS (keep alias: THINKING_ENABLED_TASKS = COMPLEX_TASKS for backward compat)
- Mark OPENROUTER_STRATEGY, OPENROUTER_FULL_MODEL, OPENROUTER_MINI_MODEL as deprecated in comments
- Fix extra_body shape inconsistency in ai_client_factory.py get_model_config() (normalize to {"extra_body": {...}} shape)
- Verify 5 consumer files still compile

Phase 1 (router):
- Create utils/llm_router.py (~250 lines)
- LLMRouter class with call(task, messages, json_output, temperature, max_tokens)
- _get_profile_and_model() method: resolves MODEL_PROFILES based on configured model + task complexity
- Profile-based routing: complex tasks get profile's complex_model + complex_params, simple tasks get simple_model + simple_params
- On fallback: switch to openai/gpt-4.1 profile (model + params change together)
- Thread-safe cost tracking using profile's cost_per_1k
- JSON retry logic (3 attempts, strip markdown fences)
- Error classification: GameLLMError for quota, retry+fallback for transient
- Module-level singleton: llm = LLMRouter()

Write unit tests in scripts/test_llm_router.py for: error classification, JSON parsing, stats tracking, profile resolution (known model, unknown model, dual-model profile, TASK_OVERRIDES).

Use the Phase 1 code block in the plan as the implementation reference.

Do NOT migrate any consumer files yet."

---

**Last Updated:** 2026-02-09
**Status:** PLANNING - Deferred until OpenAI-based TT build ships to testers
**Revision:** v3.3 - Added Combat Prompt Optimization section (P5, P6, P10-P12) for multi-model routing prep based on multi-PC combat prompt audit; covers prompt splitting, redundancy tiers, plain-text alternatives, and conditional examples

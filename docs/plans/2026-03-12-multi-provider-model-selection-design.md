# Multi-Provider Model Selection Design

**Date:** 2026-03-12
**Status:** Approved
**Purpose:** Allow users to select AI provider (Legacy/OpenAI/Gemini/LM Studio) via web UI settings, with correct model mapping per provider.

---

## Context

GPT-4.1 is being sunset by OpenAI. The game currently runs on 27 model variables across 95 API callsites, all pointing to `gpt-4.1-2025-04-14` or `gpt-4.1-mini-2025-04-14`. We need replacements selected by reliability first, then pricing and speed.

Capture testing has collected side-by-side outputs from multiple models (gpt-5.2, gpt-5.4, gpt-5-mini, gemini-3-pro, gemini-3-flash, gemini-3.1-pro, gemini-3.1-flash-lite) across 15 task IDs. The user reviews capture data and decides which model wins per callsite.

## Priority Order

1. **Reliability** - some callsites are accuracy-critical (combat validation, character sheets, JSON schemas). 80% accurate breaks the game and causes cascading errors.
2. **Pricing** - match or reduce current gpt-4.1 costs where possible
3. **Speed** - latency matters for gameplay but not at expense of correctness

---

## Design

### 1. Provider Setting (model_config.py)

Replace `USE_GPT5_MODELS` and `USE_LM_STUDIO` booleans with a single provider setting:

```python
MODEL_PROVIDER = "legacy"  # options: "legacy", "openai", "gemini", "lmstudio"
```

### 2. Provider Model Map (model_config.py)

```python
PROVIDER_MODELS = {
    "legacy": {
        "full": "gpt-4.1-2025-04-14",
        "mini": "gpt-4.1-mini-2025-04-14",
    },
    "openai": {
        "full": "gpt-5.2",           # update after capture testing completes
        "mini": "gpt-5-mini",
    },
    "gemini": {
        "full": "gemini-3.1-pro-preview",
        "mini": "gemini-3.1-flash-lite-preview",
    },
    "lmstudio": {
        "full": "local-model",
        "mini": "local-model",
    },
}
```

### 3. Tier Lookup Table (model_config.py)

Each of the 27 model variables is tagged as "full" or "mini":

```python
MODEL_TIER_MAP = {
    "DM_MAIN_MODEL": "full",
    "DM_VALIDATION_MODEL": "full",
    "DM_FULL_MODEL": "full",
    "COMBAT_MAIN_MODEL": "full",
    "CHARACTER_VALIDATOR_MODEL": "full",
    "NPC_BUILDER_MODEL": "full",
    "MONSTER_BUILDER_MODEL": "full",
    "LEVEL_UP_MODEL": "full",
    "ACTION_PREDICTION_MODEL": "full",
    "LOCATION_COMPRESSION_MODEL": "full",
    "DM_MINI_MODEL": "mini",
    "DM_SUMMARIZATION_MODEL": "mini",
    "NARRATIVE_COMPRESSION_MODEL": "mini",
    "COMBAT_DIALOGUE_SUMMARY_MODEL": "mini",
    "ADVENTURE_SUMMARY_MODEL": "mini",
    "PLOT_UPDATE_MODEL": "mini",
    "PLAYER_INFO_UPDATE_MODEL": "mini",
    "NPC_INFO_UPDATE_MODEL": "mini",
    "ENCOUNTER_UPDATE_MODEL": "mini",
    "TRANSITION_VALIDATOR_MODEL": "mini",
}
```

### 4. set_provider() Function (model_config.py)

```python
def set_provider(provider_name):
    global MODEL_PROVIDER
    MODEL_PROVIDER = provider_name
    models = PROVIDER_MODELS[provider_name]
    for var_name, tier in MODEL_TIER_MAP.items():
        globals()[var_name] = models[tier]
```

When called, this rewrites all 27 model variables in-memory. Callsites continue reading `config.DM_MAIN_MODEL` etc. with no code changes needed at the callsite level for basic provider switching.

### 5. Provider-Aware API Client (core/ai/api_client.py - new file)

```python
def create_completion(messages, model, temperature=None, **kwargs):
    provider = get_current_provider()  # reads MODEL_PROVIDER

    if provider in ("legacy", "openai"):
        return openai_client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, **kwargs
        )
    elif provider == "gemini":
        return gemini_call(model, messages, temperature, **kwargs)
    elif provider == "lmstudio":
        return lmstudio_client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, **kwargs
        )
```

- OpenAI and Legacy use the same OpenAI client (different model strings)
- LM Studio uses OpenAI-compatible API pointed at localhost:1234
- Gemini uses existing `gemini_caller.py` conversion logic
- Gemini responses are normalized to match OpenAI response shape (`.choices[0].message.content`)

### 6. Web UI Settings (game_interface.html)

Replace the existing model toggle with a provider dropdown:

```html
<div class="settings-section">
    <div class="settings-section-title">AI Provider</div>
    <div class="settings-item">
        <label for="model-provider-select">Provider</label>
        <select class="settings-select" id="model-provider-select">
            <option value="legacy">Legacy (GPT-4.1)</option>
            <option value="openai">OpenAI (GPT-5.x)</option>
            <option value="gemini">Gemini 3.1</option>
            <option value="lmstudio">LM Studio (Local)</option>
        </select>
    </div>
</div>
```

### 7. SocketIO Handler (run_web.py)

```python
@socketio.on('set_model_provider')
def handle_set_provider(data):
    provider = data.get('provider', 'legacy')
    model_config.set_provider(provider)
    persist_provider_setting(provider)  # write to disk for restart persistence
    emit('provider_changed', {'provider': provider})
```

### 8. Persistence

Provider choice persists to disk (either updating `model_config.py` directly or a separate `user_settings.json`). Survives server restarts. Default is `"legacy"`.

---

## Migration Work

### How Callsite Changes Are Applied

**CRITICAL: No automated Python search-and-replace scripts.**

Each of the 95 callsites is individually hand-patched:

1. User reviews capture data and decides which model per callsite per provider
2. User directs a subagent to apply the change at the specific file and line
3. Subagent opens the file, understands the callsite, makes the change
4. A validation agent verifies the change is correct and complete
5. The callsite must reference `model_config.py` variables (no hardcoded model strings)

The audit inventory (`docs/audit/2026-02-12-openai-api-call-inventory.json`) with T001-T095 serves as the checklist.

### What Changes Per Callsite

Each callsite needs to route through `create_completion()` instead of calling `client.chat.completions.create()` directly. This enables the provider routing. The model variable reference stays the same.

---

## Behavioral Rules

- Switching providers mid-game is allowed (no restart required)
- Legacy remains the default until capture testing validates all callsites
- The `USE_GPT5_MODELS` and `USE_LM_STUDIO` booleans are removed, replaced by `MODEL_PROVIDER`
- No prompts are modified during this work (prompts are frozen)
- Capture system continues working alongside this - Legacy provider = baseline data

---

## Files Changed

| File | Change |
|---|---|
| `model_config.py` | Add `MODEL_PROVIDER`, `PROVIDER_MODELS`, `MODEL_TIER_MAP`, `set_provider()`. Remove `USE_GPT5_MODELS`, `USE_LM_STUDIO` |
| `core/ai/api_client.py` | New file - provider-aware API wrapper |
| `web/templates/game_interface.html` | Replace model toggle with provider dropdown |
| `run_web.py` | Add `set_model_provider` SocketIO handler |
| `CLAUDE.md` | Add search-and-replace prohibition (already done) |
| 95 callsite files | Each individually patched to use `create_completion()` wrapper |

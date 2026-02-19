# Multi-Model Capture System Design

**Date:** 2026-02-18
**Status:** Approved - ready for implementation
**Context:** Part of the multi-provider model refactor. See CLAUDE.md refactor section and
`docs/reference/openai-models-reference.md` / `docs/reference/gemini-models-reference.md`.

---

## Purpose

Collect parallel telemetry from multiple AI model variants while the game runs normally on the
existing gpt-4.1 baseline. Each API callsite fires its primary gpt-4.1 call synchronously (game
unaffected), then fans out to all candidate models in background threads. Results are stored in
per-callsite JSON files for later comparison and tuning.

This is telemetry-only. No evaluation logic. No model switching. No prompt changes.

---

## Goals

- Game continues to run on gpt-4.1 with zero behavioral change
- Background capture fires all model variants for each callsite, records input/output pairs
- Response time (seconds) captured per variant for cost/speed analysis
- Find the cheapest and fastest model that matches or beats gpt-4.1 quality per callsite
- No token limits anywhere in any capture calls
- All capture data gitignored, never committed

---

## File Layout

```
model_captures/                        # gitignored root - all capture data stays local
├── capture_config.json                # model variant mapping and toggle (gitignored)
├── errors.log                         # background thread errors (never surface to game)
├── test_all_models.py                 # connectivity and return value validation script
├── T012.json                          # one file per runtime callsite (T012-T095)
├── T013.json
├── ...
└── T095.json

utils/capture/                         # capture module - committed to git
├── __init__.py
├── multi_model_capture.py             # capture_and_fanout(), thread pool, file writer
├── openai_caller.py                   # OpenAI variant caller
└── gemini_caller.py                   # Gemini caller with message format conversion
```

---

## Capture Config (`model_captures/capture_config.json`)

Gitignored. Controls which variants fire for each tier. `use_caller_temp: true` passes whatever
temperature the original callsite used; `false` omits temperature entirely (required for OpenAI
reasoning > none, and default for Gemini high-thinking variants).

**No token limits anywhere - no max_tokens, max_completion_tokens, or any output length parameter
in any variant call.**

```json
{
  "capture_enabled": true,
  "full_tier_variants": [
    { "provider": "openai", "model": "gpt-4.1-2025-04-14",     "reasoning_effort": null,    "use_caller_temp": true,  "label": "gpt-4.1|baseline" },
    { "provider": "openai", "model": "gpt-5.2",                "reasoning_effort": "none",  "use_caller_temp": true,  "label": "gpt-5.2|effort=none" },
    { "provider": "openai", "model": "gpt-5.2",                "reasoning_effort": "low",   "use_caller_temp": false, "label": "gpt-5.2|effort=low" },
    { "provider": "openai", "model": "gpt-5.2",                "reasoning_effort": "medium","use_caller_temp": false, "label": "gpt-5.2|effort=medium" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": null,    "use_caller_temp": false, "label": "gpt-5-mini" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": "low",   "use_caller_temp": false, "label": "gpt-5-mini|effort=low" },
    { "provider": "gemini", "model": "gemini-3-pro-preview",   "thinking_level": "low",     "use_caller_temp": true,  "label": "gemini-3-pro|thinking=low" },
    { "provider": "gemini", "model": "gemini-3-pro-preview",   "thinking_level": "high",    "use_caller_temp": false, "label": "gemini-3-pro|thinking=high" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "low",     "use_caller_temp": true,  "label": "gemini-3-flash|thinking=low" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "high",    "use_caller_temp": false, "label": "gemini-3-flash|thinking=high" }
  ],
  "mini_tier_variants": [
    { "provider": "openai", "model": "gpt-4.1-mini-2025-04-14","reasoning_effort": null,    "use_caller_temp": false, "label": "gpt-4.1-mini|baseline" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": null,    "use_caller_temp": false, "label": "gpt-5-mini" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": "low",   "use_caller_temp": false, "label": "gpt-5-mini|effort=low" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "low",     "use_caller_temp": false, "label": "gemini-3-flash|thinking=low" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "high",    "use_caller_temp": false, "label": "gemini-3-flash|thinking=high" }
  ],
  "task_overrides": {}
}
```

`task_overrides` allows pinning specific variant configs to individual task_ids without code
changes, for future per-callsite tuning.

---

## Capture Record Format (`model_captures/T{nnn}.json`)

Append-only JSON array. One record per callsite invocation. Background thread outputs merge into
the same record identified by `timestamp` + `task_id`. File writes are serialized with a
per-file `threading.Lock`.

```json
[
  {
    "timestamp": "2026-02-18T14:23:01Z",
    "task_id": "T013",
    "file": "core/ai/action_handler.py",
    "line": 1003,
    "tier": "full",
    "input": {
      "messages": [...],
      "temperature": 0.7,
      "reasoning_effort": "none"
    },
    "outputs": {
      "gpt-4.1|baseline":             { "content": "...", "latency_s": 0.843 },
      "gpt-5.2|effort=none":          { "content": "...", "latency_s": 0.612 },
      "gpt-5.2|effort=low":           { "content": "...", "latency_s": 0.934 },
      "gpt-5.2|effort=medium":        { "content": "...", "latency_s": 1.402 },
      "gpt-5-mini":                   { "content": "...", "latency_s": 0.341 },
      "gpt-5-mini|effort=low":        { "content": "...", "latency_s": 0.298 },
      "gemini-3-pro|thinking=low":    { "content": "...", "latency_s": 0.701 },
      "gemini-3-pro|thinking=high":   { "content": "...", "latency_s": 1.830 },
      "gemini-3-flash|thinking=low":  { "content": "...", "latency_s": 0.389 },
      "gemini-3-flash|thinking=high": { "content": "...", "latency_s": 0.812 }
    },
    "errors": {}
  }
]
```

- `input.temperature` reflects whatever the callsite actually passed (dynamic, not hardcoded)
- `errors` maps label -> error string for any variant that failed; game never sees these
- Primary gpt-4.1 output written synchronously by main thread; all others written by background
  threads as they complete

---

## `capture_and_fanout()` Wrapper

Location: `utils/capture/multi_model_capture.py`

**Signature:**
```python
def capture_and_fanout(task_id, messages, **kwargs):
    """
    Drop-in replacement for client.chat.completions.create at instrumented callsites.
    Returns the primary gpt-4.1 response synchronously. Fires all other variants in
    background threads. No token limits in any call.
    """
```

**Call pattern at each instrumented callsite:**
```python
# Before:
response = client.chat.completions.create(model=..., messages=messages, temperature=0.7)

# After:
response = capture_and_fanout("T013", messages, model=..., temperature=0.7)
```

**Execution flow:**
1. Check `capture_enabled` in config - if off, delegate directly to `client.chat.completions.create` (zero overhead)
2. Fire primary gpt-4.1 call synchronously, measure latency, record output
3. Submit all other variants to `ThreadPoolExecutor` as non-blocking futures
4. Return primary response immediately - game continues
5. Background threads each call their model, measure latency, acquire file lock, merge into record

**Thread pool:** Shared `ThreadPoolExecutor(max_workers=8)` initialized once at module import.
IO-bound API calls make 8 workers efficient. Tasks beyond 8 queue internally - nothing is dropped.

---

## API Key Sources

| Provider | Key Location | Format |
|----------|-------------|--------|
| OpenAI | `config.py` (gitignored) | `OPENAI_API_KEY = "sk-..."` |
| Gemini | `google_api.pi` (gitignored) | `api_key=AIza...` |

Both read at module init using the same patterns as the existing codebase (`config.py` import for
OpenAI, file-read for Gemini matching `gemini_tool.py` pattern).

---

## Message Format Conversion (Gemini)

OpenAI uses `[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]`.
Gemini uses `types.Content` objects with `system_instruction` as a separate parameter.

`gemini_caller.py` handles this conversion transparently:
- System message (role: "system") -> `system_instruction` parameter
- Remaining messages -> `contents` list of `types.Content` objects
- `response_mime_type="application/json"` when original call uses `response_format={"type": "json_object"}`
- `thinking_config=types.ThinkingConfig(thinking_level=...)` for reasoning control
- Temperature passed only when `use_caller_temp: true` for that variant

---

## Test Script (`model_captures/test_all_models.py`)

Sends a fixed minimal prompt (`"Respond with the word OK and nothing else."`) through every
variant in both tiers. Prints a pass/fail table with latency. Cheap to run (minimal tokens),
confirms API keys work, confirms all models are accessible, and surfaces any rate limit or
authentication issues before callsite wiring begins.

Output format:
```
Testing full tier (10 variants)...
  gpt-4.1|baseline             [PASS]  0.82s
  gpt-5.2|effort=none          [PASS]  0.61s
  gpt-5.2|effort=low           [PASS]  0.93s
  ...
  gemini-3-flash|thinking=high [PASS]  0.81s

Testing mini tier (5 variants)...
  gpt-4.1-mini|baseline        [PASS]  0.41s
  ...

Result: 15/15 passed
```

---

## Gitignore Additions Required

```
# Multi-model capture data (local telemetry only)
model_captures/
```

---

## Toggle

`MULTI_MODEL_CAPTURE = False` in `model_config.py` (default off).
Set to `True` to enable. When off, `capture_and_fanout()` is a transparent zero-overhead
pass-through to the existing OpenAI call.

---

## Constraints (Non-Negotiable)

- No token limits (`max_tokens`, `max_completion_tokens`) in any variant call, ever
- No prompt changes at any callsite - only model name and parameters change
- Primary gpt-4.1 path always runs synchronously and is never delayed
- Background errors are caught silently and logged - never propagate to game
- Every callsite instrumentation requires explicit user review and approval before implementation
- Capture data stays local, never committed

---

## Callsite Inventory Reference

Source of truth for all 95 callsites (59 runtime, scope=runtime):
`docs/audit/2026-02-12-openai-api-call-inventory.json`

Runtime callsites span T012-T095 across:
`core/ai/`, `core/generators/`, `core/managers/`, `core/validation/`,
`main.py`, `updates/`, `utils/`, `web/`

Tier assignment per callsite is determined by which config variable drives the model:
- Full tier: any callsite using a `*_MAIN_MODEL`, `*_FULL_MODEL`, `*_VALIDATION_MODEL`,
  `*_BUILDER_MODEL`, `COMBAT_MAIN_MODEL`, `LEVEL_UP_MODEL`, `ACTION_PREDICTION_MODEL`,
  `LOCATION_COMPRESSION_MODEL`, `CHARACTER_VALIDATOR_MODEL`, `DM_EFFECTS_MODEL`
- Mini tier: any callsite using `*_MINI_MODEL`, `*_SUMMARIZATION_MODEL`, `*_SUMMARY_MODEL`,
  `PLOT_UPDATE_MODEL`, `NPC_INFO_UPDATE_MODEL`, `ENCOUNTER_UPDATE_MODEL`,
  `TRANSITION_VALIDATOR_MODEL`, `NARRATIVE_COMPRESSION_MODEL`, `COMBAT_DIALOGUE_SUMMARY_MODEL`

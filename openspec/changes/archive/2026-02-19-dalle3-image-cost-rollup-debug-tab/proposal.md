## Why

Debug tab session/week USD and NZD rollups currently update from tracked LLM usage events, but DALL-E 3 image generation paths do not emit tracking events into that pipeline. Facilitators see portrait/image generation succeed while cost totals stay unchanged, which creates a false impression that image generation has no cost impact.

## What Changes

- Add DALL-E 3 image-price estimation config in `model_config.py` with explicit size/quality mapping and safe defaults.
- Add provider-agnostic cost-only event tracking in `utils/llm_usage_tracker.py` for image generation events that have no token usage payload.
- Preserve compatibility by re-exporting new tracker helpers through `utils/openai_usage_tracker.py`.
- Instrument successful DALL-E 3 generation callsites to emit one tracked image-cost event per successful generation.
- Preserve existing token counters (`tpm`, `rpm`, `total_tokens`, session/week token totals) for image-cost events.
- Add regression tests to prove Debug tab rollups change for image events while token totals remain unchanged.

### Non-goals

- No billing-grade reconciliation against provider invoices.
- No per-provider FX integration.
- No gameplay/combat behavior changes.
- No broad UI redesign for Debug tab.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `debug-tab-usage-cost-rollup`
- `provider-agnostic-usage-tracking`
- `usage-cost-conversion-policy`

## Impact

- Affected code:
  - `model_config.py`
  - `utils/llm_usage_tracker.py`
  - `utils/openai_usage_tracker.py`
  - `core/toolkit/portrait_service.py`
  - `core/toolkit/npc_generator.py`
  - `core/toolkit/monster_generator.py`
  - `web/web_interface.py`
  - `scripts/test_usage_rollups_debug_tab.py`
- API/system surfaces:
  - Existing SocketIO `token_update` remains additive and unchanged in key shape.
  - Internal usage tracker gains explicit cost-only image event method.
- Dependencies:
  - No external dependency changes.
- Rollout risk:
  - Medium (shared tracking path touched by multiple image callsites).
  - Mitigated by fail-open tracking, additive config, and regression coverage.
- Fallback strategy:
  - If image pricing config is missing/invalid, tracker records safe zero cost with unavailable source while keeping app behavior stable.
  - If tracking errors occur, image generation continues and only telemetry is degraded.
- Merge-safety/SP-MP impact:
  - Additive changes only; no behavior difference between SP and tabletop for generation success path.

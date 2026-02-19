## Why

The Debug tab currently shows only live TPM/RPM/total token counters and does not expose cost visibility for the active session or recent week. Facilitators need a quick top-level view of token and dollar usage, including USD->NZD conversion, without tying implementation to a single provider brand.

## What Changes

- Add a provider-agnostic usage aggregation layer that tracks session and rolling-week token and cost rollups.
- Preserve backward compatibility by keeping `utils/openai_usage_tracker.py` import surface functional while delegating to generic usage internals.
- Extend socket `token_update` payload to include `session_*` and `week_*` token/cost fields plus conversion metadata.
- Update Debug tab header UI to show a new top rollup bar above existing TPM/RPM/Total stats.
- Add lightweight pricing and conversion settings in `model_config.py`:
  - USD->NZD conversion rate
  - rolling-week window size
  - optional blended fallback USD-per-1M token rate (used only when provider does not return per-call cost)
- Add tests for provider-agnostic tracking, rolling-window math, and UI payload compatibility.
- Explicit non-goals:
  - No external FX API dependency in MVP.
  - No billing-grade accounting guarantees.
  - No gameplay/mechanics behavior changes.

## Capabilities

### New Capabilities
- `provider-agnostic-usage-tracking`: Generic usage tracker contracts for session/week counters and compatibility shim behavior.
- `debug-tab-usage-cost-rollup`: Debug tab top-bar presentation for session/week tokens and USD/NZD costs without regressing existing token stats.
- `usage-cost-conversion-policy`: Provider-reported cost first, with generic fallback estimation and USD->NZD conversion.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `utils/llm_usage_tracker.py` (new)
  - `utils/openai_usage_tracker.py` (compatibility shim update)
  - `model_config.py`
  - `web/web_interface.py`
  - `web/templates/game_interface.html`
  - test scripts under `scripts/`
- API/system surfaces:
  - Existing SocketIO `token_update` event gets additive fields; current fields remain unchanged.
- Dependencies:
  - No new external service required; conversion rate remains local config.
- Rollout risk:
  - Medium (shared telemetry path + UI binding).
  - Mitigated by additive payload design, compatibility shim, and provider-reported cost preference.
- Fallback strategy:
  - If provider cost is missing, usage counters still update and cost fields fall back to safe estimate/default behavior.
  - If new fields are absent in frontend payloads, UI renders zero values and preserves existing TPM/RPM/Total.
- Merge-safety/SP-MP impact:
  - Additive extension-first change with minimal host edits; no change to single-player or tabletop gameplay flow.

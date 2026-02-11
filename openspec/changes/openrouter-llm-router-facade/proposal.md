## Why

NeverEndingQuest currently routes most LLM calls through mixed direct client usage, which makes provider switching, fallback behavior, and callsite migration error-prone. We need a single facade layer now so future OpenRouter rollout can be staged safely without breaking upstream-compatible single-player behavior.

## What Changes

- Add an `llm.call(...)` facade API that centralizes provider selection, model profile resolution, and common call defaults for chat completions.
- Define role/capability-driven model profile infrastructure so callsites reference intent (for example narration, mechanics, validation) instead of hardcoded model IDs.
- Add standardized provider failure handling for timeouts, quota/rate limits, and transient transport errors with deterministic fallback path.
- Add router-level observability hooks (provider/model/role usage counters and error-class metrics) for migration verification.
- Add a compatibility mode contract: no behavior change for existing OpenAI path when multiplayer-specific routing is not active.
- Explicit non-goals for this change:
  - No full migration of all existing LLM callsites (handled by `openrouter-llm-callsite-migration`).
  - No image/TTS provider migration in this phase.
  - No changes to game mechanics/state persistence rules.

## Capabilities

### New Capabilities
- `llm-router-facade`: Unified facade entrypoint and routing contract for LLM chat operations.
- `model-profile-routing`: Capability/role-based model profile selection, fallback policy, and provider error classification.

### Modified Capabilities
- None.

## Impact

- Affected code: `utils/llm_router.py` (new), `model_config.py`, and integration touchpoints that currently choose models/clients directly.
- APIs: introduces a stable internal API (`llm.call`) to decouple business logic from provider client specifics.
- Dependencies/systems: uses existing OpenAI/OpenRouter client wiring and extends it with unified routing policy, error handling, and telemetry.
- Rollout risk: medium, because routing sits in shared LLM plumbing; mitigated via staged activation, compatibility defaults, and explicit fallback to OpenAI on provider outage.
- Provider outage/quota behavior: router must classify retryable vs non-retryable errors, auto-fallback when allowed, and surface hard-stop errors clearly when both providers are unavailable.
- Merge-safety/SP-MP impact: implementation stays in extension-oriented modules with minimal host-file hooks; single-player mode remains backward-compatible while tabletop/multiplayer can opt into router behavior.

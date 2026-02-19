## Context

The Debug tab receives cost rollups from `get_usage_stats()` and renders session/week USD and NZD values. Those values only change when the usage tracker receives tracked events. Current chat/completion paths call tracker methods, but image generation paths (`images.generate`) do not, so image requests are invisible to rollups.

Constraints:
- Preserve existing token and cost socket payload keys and semantics.
- Keep image generation success/failure behavior unchanged.
- Keep tracker thread-safe and fail-open.
- Keep Python-visible text ASCII-only.

## Goals / Non-Goals

**Goals:**
- Track successful DALL-E 3 image generation into session/week cost rollups.
- Keep token counters unchanged for image-cost events.
- Use explicit model pricing config for deterministic estimates when provider cost is unavailable.
- Preserve compatibility imports via `utils/openai_usage_tracker.py`.

**Non-Goals:**
- Multi-provider image billing parity in this change.
- Exact invoice matching.
- UI redesign beyond existing rollup bindings.

## Decisions

### 1) Add explicit DALL-E 3 pricing config
Decision: add DALL-E 3 per-image pricing map in `model_config.py`, keyed by size and quality.

Rationale:
- Image APIs usually do not expose token usage in the same shape as chat/completions.
- Explicit config keeps estimates deterministic and operator-visible.

Alternatives considered:
- Keep only blended token fallback: rejected because image events have no reliable token count.

### 2) Add cost-only image event tracking path
Decision: add a tracker method that records cost rollup events without token usage deltas.

Rationale:
- Prevents fake token inflation.
- Reuses existing session/week cost aggregation infrastructure.

Alternatives considered:
- Inject synthetic token counts: rejected as misleading telemetry.

### 3) Instrument all successful `images.generate` callsites
Decision: add fail-open tracking calls after successful generation in all known DALL-E paths.

Rationale:
- Ensures portrait create, toolkit NPC/monster generation, and socket image generation all contribute to rollups.

Alternatives considered:
- Track only portrait endpoint: rejected due to incomplete coverage.

### 4) Track exactly one event per successful generation
Decision: emit tracking after the final successful call in retry/sanitization paths.

Rationale:
- Avoids double counting for content-policy retry flows.

Alternatives considered:
- Track every attempt: rejected due to user-facing cost confusion.

### 5) Keep failure isolation as hard invariant
Decision: all tracking failures are non-fatal and MUST NOT block image generation responses.

Rationale:
- Gameplay and toolkit operations must remain reliable even when telemetry fails.

## Risks / Trade-offs

- [Pricing table drift from provider pricing changes] -> Mitigation: keep values centralized in config with explicit labels and easy updates.
- [Missed callsite causes partial rollups] -> Mitigation: instrument all discovered `images.generate` paths and add regression tests.
- [Concurrent writes from web/toolkit threads] -> Mitigation: continue lock-protected tracker updates.

## Migration Plan

1. Add DALL-E 3 pricing config and tracker image-cost API.
2. Add compatibility export through `utils/openai_usage_tracker.py`.
3. Instrument successful image generation callsites.
4. Add regression tests for cost-only rollups and token invariants.
5. Run compile and test verification.

Rollback strategy:
- Disable image tracking callsites (or short-circuit helper) while preserving existing token tracking.
- Keep pricing config additive; it can remain unused safely.

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile model_config.py utils/llm_usage_tracker.py utils/openai_usage_tracker.py core/toolkit/portrait_service.py core/toolkit/npc_generator.py core/toolkit/monster_generator.py web/web_interface.py`
- Tests:
  - `python3 scripts/test_usage_rollups_debug_tab.py`
- Functional checks:
  - One successful DALL-E generation increases session/week USD/NZD.
  - Token counters remain unchanged for the image-cost event.
  - Retry path records one final success event only.

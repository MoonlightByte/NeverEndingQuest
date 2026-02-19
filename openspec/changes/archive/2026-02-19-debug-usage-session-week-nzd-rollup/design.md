## Context

Usage tracking currently exists behind OpenAI-named helpers and is emitted to the web Debug tab as TPM/RPM/total only. The requested feature adds session and week-level usage + cost visibility and must remain provider-agnostic for OpenRouter and future provider routing.

Constraints:
- Preserve existing SocketIO `token_update` consumers and existing UI fields.
- Keep single-player and tabletop behavior unchanged.
- Maintain thread safety for web + background worker contexts.
- Keep Python console/log output ASCII-safe.

Stakeholders:
- Facilitators: need a quick gameplay cost indicator during sessions.
- Maintainers: need merge-safe, provider-neutral telemetry contracts.
- Future router migration: needs non-provider-specific tracker naming and cost parsing.

## Goals / Non-Goals

**Goals:**
- Provide session and rolling-week token/cost rollups.
- Show USD and NZD values in Debug tab header above existing token stats.
- Decouple usage tracker API naming from provider branding.
- Prefer provider-reported per-call cost when available.
- Keep old `openai_usage_tracker` imports working to avoid broad refactors.
- Keep additive payload compatibility for frontend and any external listeners.

**Non-Goals:**
- Exact invoice reconciliation with provider dashboards.
- Real-time FX API integration.
- Per-model or per-image detailed billing breakdown in GUI.
- Cross-provider image/TTS billing integration in this change.

## Decisions

### 1) Introduce Generic Tracker Module + Compatibility Shim
Decision: add `utils/llm_usage_tracker.py` as primary implementation and make `utils/openai_usage_tracker.py` a backward-compatible wrapper/re-export layer.

Rationale:
- Enables provider-neutral naming now.
- Avoids high-risk callsite churn across many files.

Alternatives considered:
- Rename all imports in one sweep: rejected due to high blast radius.

### 2) Keep Additive Socket Contract
Decision: preserve `tpm`, `rpm`, `total_tokens` and add new fields (`session_*`, `week_*`, conversion metadata, cost source metadata).

Rationale:
- Prevents frontend regressions.
- Allows phased UI adoption and external consumer compatibility.

Alternatives considered:
- Replace payload schema entirely: rejected due to no-regression requirement.

### 3) Cost Source Strategy: Provider-Reported First
Decision: use provider-reported cost from usage metadata when present; otherwise use a single blended fallback estimate per 1M tokens.

Config:
- `USD_TO_NZD_RATE`
- `USAGE_WEEK_WINDOW_DAYS`
- `USD_PER_1M_TOKENS_BLEND` (fallback only)

Rationale:
- Aligns with OpenRouter usage accounting and future provider APIs.
- Keeps implementation lightweight and provider-agnostic.
- Avoids brittle per-model pricing maintenance in codebase.

Alternatives considered:
- Per-model pricing map in app config: rejected as unnecessary for the DM-facing total indicator.

### 4) Rolling-Week from Timestamped Usage Events
Decision: maintain in-memory rolling history and compute week totals using timestamped usage events; bootstrap from telemetry log if present, while tolerating malformed lines.

Rationale:
- Supports current-session and recent-week visibility.
- Reuses existing telemetry direction without adding DB migrations.

Alternatives considered:
- Persist week totals in DB: rejected for MVP complexity.

### 5) Explicit Cost Confidence Metadata
Decision: emit metadata for cost confidence and source (`cost_estimate`, `cost_source`) so UI can present totals without claiming billing-grade precision.

Rationale:
- Avoids false precision while still giving actionable live guidance.
- Keeps tracker useful when provider cost field is unavailable.

Alternatives considered:
- Hide costs when provider does not return cost: rejected as poor UX.

## Risks / Trade-offs

- [Rolling-week file bootstrap can be expensive on very large logs] -> Mitigation: bounded parse strategy and lazy-safe fallback to in-memory only when parse fails.
- [Provider cost units/fields vary by provider] -> Mitigation: parse documented OpenAI-compatible usage fields first and tag `cost_source`.
- [Fallback blended rate is approximate] -> Mitigation: mark fallback as estimated and keep dashboards as source of truth.
- [Concurrency races in shared counters] -> Mitigation: lock-protected state updates and read snapshots; avoid nested lock acquisition.
- [Legacy import breakage] -> Mitigation: compatibility shim with same function names and behavior contract.

## Migration Plan

1. Add generic tracker module and compatibility shim.
2. Add minimal config constants for conversion, week window, and blended fallback rate.
3. Extend web socket emitter with additive fields and cost metadata.
4. Add Debug tab top rollup row and JS bindings.
5. Add tests for rollup math, provider-cost parsing, fallback behavior, and payload compatibility.
6. Run compile + smoke checks.

Rollback strategy:
- Revert Debug tab bindings and token payload extension.
- Keep compatibility shim intact; disable cost fields by returning zero values.
- Preserve existing TPM/RPM/Total path as last-known-good behavior.

## Open Questions

- Should `USD_PER_1M_TOKENS_BLEND` default to a conservative value or `0.0` (forcing "unavailable" when no provider cost)?
- Should UI label fallback values as "Estimated" inline or in tooltip-only text?

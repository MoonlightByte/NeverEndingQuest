## Context

NeverEndingQuest has mixed LLM invocation patterns (direct `OpenAI()` calls, partial factory usage, and task-level model constants), which increases migration risk and creates inconsistent error handling. This change establishes a thin facade over existing factory infrastructure so callsites can migrate in phases without changing gameplay contracts.

This work sits at a shared architecture boundary and must preserve plugin merge safety:
- Upstream-friendly default behavior remains intact.
- TABLETOP MODE extensions continue to use minimal host-file hooks.
- Mechanical game state remains Python truth and is not altered by router policy.

Stakeholders:
- Gameplay users (reliability, latency, predictable failure behavior)
- Maintainers (merge-safe architecture and easier callsite migration)
- Testers/operators (visibility into provider/fallback usage)

## Goals / Non-Goals

**Goals:**
- Provide one internal facade (`llm.call`) for chat-based LLM operations.
- Separate responsibilities across config (profiles/policies), factory (client creation/provider detection), and facade (routing/normalization/observability).
- Ensure deterministic fallback behavior for provider outages, timeouts, and transient errors.
- Add thread-safe usage/error statistics for migration verification.
- Enable profile/capability-based model routing to avoid model-ID lock-in.

**Non-Goals:**
- Full migration of all 80+ callsites in this change.
- Replacing `ai_client_factory.py` client creation logic.
- Image generation, TTS migration, or non-chat endpoint routing.
- Changing combat/state machine mechanics or persistence semantics.

## Decisions

### 1) Keep Facade-Over-Factory Boundary
Decision: `utils/llm_router.py` calls `create_chat_client()` and `handle_provider_error()` from `utils/ai_client_factory.py` instead of reimplementing provider plumbing.

Rationale:
- Reuses existing tested fallback/client behavior.
- Keeps router focused on call normalization, profile selection, and metrics.

Alternatives considered:
- Move all factory logic into router: rejected due to duplication and higher regression risk.

### 2) Route by Task Capability via Model Profiles
Decision: router resolves model and extra params through profile configuration keyed by role/task complexity, not hardcoded per callsite.

Rationale:
- Allows model swaps by config only.
- Supports mixed profiles (different complex/simple models) without code edits.

Alternatives considered:
- One hardcoded model map in router: rejected (high lock-in, harder operations).

### 3) Define Explicit Error Classes and Outcomes
Decision: router classifies failures into retryable transient errors vs hard-stop errors.

Outcomes:
- Retryable: timeout, connection reset, 429, 502/503/504 => retry/fallback path.
- Hard-stop: invalid key, quota exhausted across providers, malformed auth => return explicit failure and avoid silent loops.

Alternatives considered:
- Treat all failures as retryable: rejected (can mask quota/auth issues and increase latency).

### 4) Thread-Safe Observability in Router
Decision: store usage/error/fallback counters behind a lock in router-owned stats structure.

Rationale:
- Web server and background actions can issue concurrent LLM calls.
- Metrics must remain accurate for rollout verification and incident debugging.

Alternatives considered:
- Non-locked counters: rejected (races and negative trust in telemetry).

### 5) Preserve Backward-Compatible Runtime Defaults
Decision: if router is unavailable for a call path or profile resolution fails, behavior falls back to existing OpenAI-compatible path with no gameplay schema changes.

Rationale:
- Maintains SP stability and merge-safety.
- Allows phased migration with low blast radius.

Alternatives considered:
- Fail closed on router initialization errors: rejected for this phase because it blocks gameplay unnecessarily.

## Risks / Trade-offs

- [Routing in shared plumbing can regress many flows] -> Mitigation: phased callsite migration, compile checks, and smoke tests on narration + combat paths before broad rollout.
- [Fallback can hide provider quality drift] -> Mitigation: explicit fallback counters and user-facing provider-switch notifications.
- [Profile config mistakes select wrong models/params] -> Mitigation: startup validation of required profile fields and safe defaults.
- [Retry logic can increase latency] -> Mitigation: bounded retries, per-call timeout caps, and hard-stop classes.
- [Thread-safe stats add small overhead] -> Mitigation: lock only around counter updates, not around network calls.

## Migration Plan

1. Implement facade and profile config scaffolding behind current defaults.
2. Add router unit tests for profile resolution, error classes, fallback transitions, and stats updates.
3. Migrate a narrow pilot set of low-risk callsites.
4. Run gameplay smoke tests (startup, narration, combat validate, summaries) and verify no-regression behavior.
5. Proceed to separate migration change (`openrouter-llm-callsite-migration`) for wider callsite adoption.

Rollback strategy:
- Repoint pilot callsites to pre-router invocation path.
- Keep `LLM_PROVIDER="openai"` and disable profile-specific behavior.
- Preserve router code in place but inactive for quick reattempt.

## Open Questions

- Should router expose a structured event hook for web UI status escalations (for example StatusTimer integration), or keep UX messaging at callsites?
- Should profile selection support explicit per-task profile overrides in phase 1, or defer all overrides to phase 2 migration?
- What minimum smoke test matrix is required before enabling router-backed paths in tabletop sessions?

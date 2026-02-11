## Context

NeverEndingQuest currently uses a mixed LLM invocation model: some paths use centralized provider-aware helpers, while other high-risk paths still call clients/models directly. This increases operational risk (timeouts, quota failures, inconsistent fallback behavior), complicates debugging, and slows OpenRouter adoption. The migration must preserve merge-safe plugin boundaries, avoid upstream structure churn, and keep single-player behavior stable while tabletop multiplayer remains deterministic.

## Goals / Non-Goals

**Goals:**
- Complete callsite migration to shared provider-aware routing/factory patterns for remaining LLM paths.
- Enforce consistent timeout, retry, and fallback behavior across narration, combat, validation, and summarization.
- Preserve backward compatibility for both single-player and tabletop multiplayer modes.
- Improve observability with consistent provider/fallback logging categories and usage metrics.
- Keep architecture model-agnostic using capability/profile routing, not hardcoded provider-specific behavior.

**Non-Goals:**
- No redesign of combat logic, tabletop turn management, or narrative mechanics.
- No migration of non-LLM subsystems (TTS/image pipelines) in this change.
- No removal of OpenAI support.
- No broad upstream host file rewrites; only minimal hooks where required.

## Decisions

1. Use tiered migration sequencing by operational risk.
   - Rationale: Migrate critical gameplay paths first (combat/main loop), validate stability, then expand to medium and low-risk callsites.
   - Alternatives considered: big-bang migration of all files at once. Rejected due to high rollback complexity and broad regression surface.

2. Standardize on capability/profile-based model selection.
   - Rationale: Avoid provider/model lock-in and keep role-based behavior stable as model inventory changes.
   - Alternatives considered: direct model constants per callsite. Rejected due to drift, inconsistent tuning, and difficult fallback management.

3. Keep fallback behavior transparent and automatic for retryable provider failures.
   - Rationale: Gameplay continuity is higher priority than provider purity; fallback must be immediate for interactive sessions.
   - Alternatives considered: fail-fast on provider errors. Rejected because it interrupts sessions for transient upstream outages.

4. Maintain architecture boundaries: config -> profile mapping, factory/router -> client selection/fallback, callsites -> role intent only.
   - Rationale: Clear boundaries reduce merge conflicts and make future provider changes isolated.
   - Alternatives considered: embedding fallback and model logic directly in each manager/module. Rejected due to duplication and drift risk.

5. Preserve thread-safety and metrics updates for shared status/counters.
   - Rationale: web and combat flows may run concurrently; shared provider/fallback metrics must avoid races.
   - Alternatives considered: best-effort unsynchronized counters. Rejected due to inaccurate telemetry and debugging blind spots.

## Risks / Trade-offs

- [Risk] Partial migration leaves mixed behavior and hidden regressions. -> Mitigation: explicit tier checklist with file inventory and completion gating.
- [Risk] Provider outage/quota behavior differs by endpoint and exception shape. -> Mitigation: normalize retryable error classes in shared utility and add integration tests.
- [Risk] Prompt-sensitive callsites regress from changed temperature/profile defaults. -> Mitigation: preserve existing temperature unless explicitly moved to profile config and validate against baseline transcripts.
- [Risk] Merge conflicts in host files during upstream sync. -> Mitigation: prefer utility-layer edits and mark unavoidable host changes with `# TABLETOP MODE:`.
- [Trade-off] Added indirection through router/factory. -> Benefit: consistent behavior and easier provider switching at scale.

## Migration Plan

1. Inventory remaining direct/model-hardcoded callsites and classify into high/medium/low risk tiers.
2. Migrate high-risk tier first (combat + core narration loops), preserving existing prompts and behavior contracts.
3. Run targeted validation after each tier (syntax, smoke gameplay flows, provider fallback tests).
4. Migrate medium and low tiers using the same pattern and verification gates.
5. Remove redundant local fallback code only after equivalent shared behavior is confirmed.
6. Publish migration completion report with remaining follow-ups, if any.

Rollback strategy:
- Revert the latest tier batch if regressions appear.
- Force provider configuration to OpenAI path as immediate operational fallback.
- Keep legacy-compatible paths until tier validation passes.

## Open Questions

- Should provider fallback notifications be emitted to players in all modes or only debugging/admin contexts?
- Which minimum automated regression suite should be mandatory before marking each tier done?
- Do we standardize timeout values globally now or keep role-specific overrides documented in model profiles?

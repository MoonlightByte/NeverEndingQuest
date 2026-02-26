## Titan v2 Alignment Stub

- Umbrella reference: `plans/version-2/titan-integration.md`
- Retune status: Pending (OpenSpec proposal not yet updated for Titan worker callsites)
- Last tagged: 2026-02-26
- Retune focus: include Titan cycle callsites in migration tiers with non-blocking error contracts and segmented usage metrics

## Why

The repository has mixed LLM call patterns (direct OpenAI clients, partial factory usage, and model constants) across high-impact gameplay paths, which increases outage risk and makes provider fallback behavior inconsistent. We need a structured migration now to complete OpenRouter-ready callsite routing without breaking single-player compatibility or upstream merge safety.

## What Changes

- Complete a tiered migration of remaining LLM callsites to centralized provider-aware routing utilities and model-profile selection.
- Standardize timeout, retry, and provider fallback behavior for combat, narration, validation, and summarization call paths.
- Remove or isolate legacy direct-client call patterns where they duplicate router/factory behavior.
- Add explicit non-goals: no gameplay mechanic changes, no schema redesign, no destructive refactors of upstream host structure, and no forced removal of OpenAI support.
- Define rollout and rollback strategy: migrate by risk tier, validate each tier, and keep feature-flag/provider fallback paths available for fast recovery.

## Capabilities

### New Capabilities
- `openrouter-llm-callsite-migration`: Capability for deterministic, provider-aware LLM invocation behavior across all targeted callsites with clear fallback and validation gates.

### Modified Capabilities
- None.

## Impact

- Affected code: `main.py`, `core/managers/combat_manager.py`, `core/ai/*`, `updates/*`, and shared LLM utility modules.
- Reliability impact: improved provider outage/quota handling via consistent fallback behavior and shared timeout/retry patterns.
- Merge-safety impact: host-file edits remain minimal and marked with `# TABLETOP MODE:` while routing logic stays in extension/utility layers.
- SP/MP compatibility: preserve dual-mode behavior (single-player remains functional, tabletop multiplayer routing remains deterministic).
- Dependencies: continued use of OpenAI SDK and OpenRouter-compatible configuration; no new external service required beyond configured providers.
- Risk and fallback: phased rollout by callsite tier, per-tier verification before expansion, immediate fallback to OpenAI-enabled paths on provider errors.

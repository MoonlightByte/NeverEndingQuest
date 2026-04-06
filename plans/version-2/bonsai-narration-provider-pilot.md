# Bonsai Narration Provider Pilot

Status: Planned version-2 pilot
Date: 2026-04-06
Owner: NEQ runtime/provider routing
Scope: Narrow local-provider evaluation for live narrator turns only

---

## 1) Purpose

This pilot evaluates whether the local Bonsai 8B 1-bit model, exposed through `bonsai api`, is good enough to serve NEQ's live narration path without widening risk into validation, combat, or structured state-mutation routing.

The goal is not to replace the current provider stack. The goal is to answer one bounded question with clean evidence:

`Can Bonsai handle NEQ's `dm_main` narration path with acceptable quality, latency, and failure behavior?`

---

## 2) Why This Is a Pilot Instead of a Full Provider Migration

NEQ already has a provider seam in `utils/ai_client_factory.py`, but the runtime is not fully centralized behind one universal router yet.

Current constraints:

1. Many call sites still use direct `OpenAI(...)` paths.
2. Structured validation, combat, and builder flows are more sensitive than freeform narration.
3. A local provider experiment must be easy to back out if prose quality, action-discipline, or availability is not good enough.

Because of that, this work MUST remain a bounded narration-only pilot.

It SHOULD inform the broader provider-routing plan in `plans/version-2/openrouter_llm_router_architecture.md`, but it MUST NOT expand into that larger migration during this slice.

---

## 3) Pilot Scope

### In Scope

1. Add `bonsai` as a third chat-provider option alongside `openai` and `openrouter`.
2. Add explicit Bonsai config values for OpenAI-compatible local API access.
3. Route only the `dm_main` narration task to Bonsai when pilot mode is enabled.
4. Fail closed for narration in pilot mode when Bonsai is unavailable or unhealthy.
5. Keep the Bonsai server lifecycle operator-managed: NEQ connects to Bonsai, but does not launch `bonsai api` for the pilot.
6. Add targeted verification proving that non-narration tasks remain on the existing provider path.

### Out of Scope

1. Validation model migration.
2. Combat simulation migration.
3. Structured JSON action generation migration beyond the live narrator path.
4. Builder/toolkit/provider migration.
5. Full callsite migration away from direct `OpenAI(...)` usage.
6. Automatic background launch or supervision of `bonsai api`.
7. Broad GUI controls for provider selection.

---

## 4) Runtime Contract

### 4.1 Pilot Activation

The pilot MUST be explicitly enabled by configuration.

It MUST NOT silently activate simply because a local Bonsai server happens to be reachable.

### 4.2 Routing Boundary

When the pilot is enabled:

1. `dm_main` narration MUST route to Bonsai.
2. Validation, combat, summaries, builders, and all other non-allowlisted tasks MUST continue using the existing provider path.

### 4.3 Failure Behavior

For this test run, Bonsai narration MUST fail closed.

That means:

1. If Bonsai is unreachable, the narration path MUST return an explicit provider failure.
2. It MUST NOT silently fall back to OpenAI or OpenRouter during the pilot.
3. Non-narration tasks MUST remain unaffected by Bonsai narration failure.

### 4.4 Process Ownership

The pilot MUST assume that the operator starts `bonsai api` manually.

NEQ SHOULD perform a bounded health/connectivity check before use, but it MUST NOT try to spawn or manage the Bonsai process during this slice.

---

## 5) Expected Implementation Surface

Likely touchpoints:

1. `utils/ai_client_factory.py`
2. `model_config.py`
3. `config_template.py`
4. Selected narrator call sites that currently hardcode `DM_MAIN_MODEL`
5. Targeted regression or smoke tests for provider routing and fail-closed behavior

This pilot SHOULD stay narrow enough that rollback means disabling the pilot config, not undoing a broad provider rewrite.

---

## 6) Observability and Test Method

The pilot should produce clean evidence for review, not anecdotal impressions only.

Evidence to collect:

1. Local Bonsai health/API reachability.
2. Proof that `dm_main` requests are routed to Bonsai when enabled.
3. Proof that non-allowlisted tasks still route to the existing provider path.
4. Clear failure output when Bonsai is down.
5. Subjective live-play notes on narration quality, pacing, and coherence.

Suggested smoke passes:

1. Simple scene narration turn.
2. Direct DM adjudication question that still goes through narration path.
3. A turn that triggers validation or state mutation elsewhere, proving those paths remain unchanged.
4. Bonsai-down failure case with explicit fail-closed behavior.

---

## 7) Risks and Trade-offs

1. [Narration quality is fast but shallow] -> Mitigation: keep scope limited to `dm_main` pilot only and review real transcripts.
2. [Pilot accidentally bleeds into structured tasks] -> Mitigation: explicit task allowlist and targeted routing tests.
3. [Silent fallback hides whether Bonsai is truly being exercised] -> Mitigation: fail closed for narration during the pilot.
4. [Auto-launch complexity obscures provider-quality evaluation] -> Mitigation: manual `bonsai api` ownership for this slice.
5. [Future router work gets coupled too early] -> Mitigation: treat this as a bounded pilot that informs, but does not replace, broader router planning.

---

## 8) Relationship to Other Version-2 Plans

This pilot is adjacent to, but distinct from, `plans/version-2/openrouter_llm_router_architecture.md`.

The router plan remains the broader architecture effort.

This Bonsai pilot SHOULD be treated as a narrow empirical experiment using today's factory seam, not a commitment to a full local-provider migration.

It also MUST remain subordinate to the repo's current sequencing rule: runtime authority stability still matters more than broad provider churn.

---

## 9) Exit Criteria

The pilot is successful if all of the following are true:

1. `dm_main` narration can be routed to Bonsai without widening provider changes into unrelated tasks.
2. Bonsai failures are explicit and fail closed for narration.
3. Non-narration tasks remain unchanged.
4. Live narration quality is good enough to justify a larger experiment.
5. The rollback path is trivial: disable the pilot configuration and return fully to the existing provider stack.

If these conditions are not met, the pilot should be considered informative but unsuccessful, and the code should remain easy to disable or revert without broader architecture impact.

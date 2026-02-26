# OpenClaw Extraction Execution Checklist

Status: Execution companion
Date: 2026-02-18
Primary plan: `plans/version-2/CNS build/openclaw.md`
Related architecture plans:
- `plans/version-2/openrouter_llm_router_architecture.md`
- `plans/version-2/CNS build/EGO.md`

---

## Purpose

This is the compact, session-by-session execution checklist for implementing the OpenClaw pattern extraction in NEQ.

Use this file while building.
Use `plans/version-2/CNS build/openclaw.md` for full rationale and references.

---

## Non-Negotiables

- [ ] Python remains mechanical truth.
- [ ] No OpenClaw gateway/daemon architecture added to NEQ runtime.
- [ ] All write-side retries are idempotent before broad fallback rollout.
- [ ] Combat/mechanics-critical tasks keep strict fail-safe behavior.
- [ ] All new behavior has regression coverage for SP and tabletop multiplayer.

---

## Quick Reading Order Before Coding

- [ ] Read `plans/version-2/CNS build/openclaw.md` sections 4, 6, 7, 9.
- [ ] Re-read `plans/version-2/openrouter_llm_router_architecture.md` sections on facade + fallback.
- [ ] Re-read `plans/version-2/CNS build/EGO.md` boundary contract and phase gates.

---

## Track 1: OpenRouter Foundation (Day-by-Day)

### Day 0 - Preflight and contract lock

- [ ] Finalize error taxonomy in one place:
  - `auth`, `rate_limit`, `timeout`, `billing`, `invalid_request`, `transient`, `fatal`.
- [ ] Define fallback transition matrix (profile rotate vs model fallback vs fail-fast).
- [ ] Lock session identity key for stickiness behavior.
- [ ] Mark mechanics-critical task list and stricter policy per task.

Exit criteria:
- [ ] Single, unambiguous taxonomy + transition comments in code/doc.

---

### Day 1 - Router run envelope

Targets:
- `utils/llm_router.py`
- `utils/ai_client_factory.py`

Checklist:
- [ ] Add router run envelope fields (`run_id`, task, provider/model requested+used, profile, attempts, fallback chain, latency, success, error_class).
- [ ] Emit/store envelope for all router-mediated calls.
- [ ] Ensure envelope data is ASCII-safe in logs.

Verification:
- [ ] Unit test confirms envelope exists for success path.
- [ ] Unit test confirms envelope exists for failure path.

---

### Day 2 - Profile store + cooldown/disable engine

Targets:
- `utils/llm_profile_store.py` (new)
- `utils/llm_router.py`
- `model_config.py`

Checklist:
- [ ] Add profile state store with atomic writes.
- [ ] Add `cooldown_until` and `disabled_until` separation.
- [ ] Add reason-aware updates (`billing` -> disabled window).
- [ ] Add expiry cleanup logic for stale cooldowns.

Verification:
- [ ] Test exponential cooldown progression.
- [ ] Test billing disable window behavior.
- [ ] Test expiry cleanup resets profile usability.

---

### Day 3 - Error-class fallback matrix

Targets:
- `utils/llm_router.py`
- `utils/ai_client_factory.py`

Checklist:
- [ ] Map each error class to action:
  - profile rotate,
  - model fallback,
  - fail-fast.
- [ ] Ensure deterministic ordering and no silent branching.
- [ ] Add structured logging for fallback decisions.

Verification:
- [ ] Matrix tests for all error classes.
- [ ] No class falls through to ambiguous behavior.

---

### Day 4 - Session stickiness

Targets:
- `utils/llm_router.py`
- session metadata surface already used in NEQ

Checklist:
- [ ] Add session-level profile/model pinning.
- [ ] Rotate only on explicit triggers:
  - new session,
  - profile unusable,
  - explicit reset.
- [ ] Prevent cross-session leakage.

Verification:
- [ ] Same session remains pinned under normal operation.
- [ ] Failure forces deterministic rotation.

---

### Day 5 - Idempotency for write-side actions

Targets:
- `utils/idempotency.py` (new)
- `core/ai/action_handler.py`
- `updates/update_character_info.py`
- `updates/update_encounter.py`

Checklist:
- [ ] Add deterministic idempotency key generation at write boundaries.
- [ ] Add short-lived replay ledger for completed write actions.
- [ ] On retry, return prior outcome instead of re-applying.

Verification:
- [ ] Simulated retry does not duplicate HP updates.
- [ ] Simulated retry does not duplicate encounter changes.
- [ ] Simulated retry does not duplicate plot updates.

---

### Day 6 - Router operator diagnostics

Targets:
- `scripts/router_status.py` (new)
- optional `scripts/router_probe.py` (new)

Checklist:
- [ ] Show active provider/model/profile.
- [ ] Show fallback chain and last error classes.
- [ ] Show cooldown/disabled profile state and remaining windows.
- [ ] Keep output concise and tabletop-friendly.

Verification:
- [ ] Operator can diagnose router state in under 30 seconds.

---

### Day 7 - Regression hardening and smoke

Targets:
- `scripts/test_llm_router_failover.py` (new)
- `scripts/test_llm_router_stickiness.py` (new)
- `scripts/test_llm_router_idempotency.py` (new)

Checklist:
- [ ] Add unit + integration tests for all new routing behaviors.
- [ ] Run existing combat and multiplayer regressions.
- [ ] Validate no deterministic mechanics regressions.

Verification gates:
- [ ] Compile checks pass.
- [ ] New router tests pass.
- [ ] Existing combat regression suites pass.

---

## Track 2: EGO Follow-on (after Track 1 complete)

### Day 8 - Passive ingestion only

Checklist:
- [ ] Ingest router envelopes into memory/event surfaces.
- [ ] No prompt writes.
- [ ] Build simple session report from telemetry.

Verification:
- [ ] Report shows fallback frequency, latency, retries, and error classes by task.

---

### Day 9 - EGO classifier augmentation

Checklist:
- [ ] Add router condition context to DRIFT/DISTORTION/HALLUCINATION output.
- [ ] Correlate divergence events with fallback/error patterns.

Verification:
- [ ] EGO report can identify whether divergence is model behavior, provider instability, or prompt issue.

---

### Day 10 - Bounded EGO adjustments (Tier 1a only)

Checklist:
- [ ] Enable canary-only, low-risk adjustments.
- [ ] Enforce per-session adjustment budget and cooldown.
- [ ] Add auto-rollback trigger.

Verification:
- [ ] No mechanics regressions.
- [ ] Adjustment audit trail is complete and reversible.

---

## Global Acceptance Gates

Ship Track 1 only if all are true:

- [ ] Router envelope coverage complete.
- [ ] Error taxonomy and fallback matrix fully tested.
- [ ] Idempotency protection present for write actions.
- [ ] Router diagnostics operational.
- [ ] Combat and multiplayer regression suites clean.

Enable Track 2 only if all are true:

- [ ] Track 1 gates complete.
- [ ] EGO passive telemetry quality is acceptable.
- [ ] Rollback and audit trails verified.

---

## Session Template (copy into daily notes)

Use this mini template at start/end of each implementation session.

Start:
- [ ] Day number:
- [ ] Target files:
- [ ] Intended behavior change:
- [ ] Risk notes:

End:
- [ ] What was implemented:
- [ ] Tests run:
- [ ] Pass/fail:
- [ ] Follow-up tasks:
- [ ] Blockers:

---

## Pointers to OpenClaw reference examples

- Failover behavior docs:
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/model-failover.md
- Profile order and cooldown internals:
  - https://github.com/openclaw/openclaw/blob/main/src/agents/auth-profiles/order.ts
  - https://github.com/openclaw/openclaw/blob/main/src/agents/auth-profiles/usage.ts
- Session stickiness logic:
  - https://github.com/openclaw/openclaw/blob/main/src/agents/auth-profiles/session-override.ts
- Health summary shape:
  - https://github.com/openclaw/openclaw/blob/main/src/agents/auth-health.ts
- Model status and scanning UX:
  - https://github.com/openclaw/openclaw/blob/main/src/commands/models/list.status-command.ts
  - https://github.com/openclaw/openclaw/blob/main/src/commands/models/scan.ts
- Idempotency schema precedent:
  - https://github.com/openclaw/openclaw/blob/main/src/gateway/protocol/schema/agent.ts

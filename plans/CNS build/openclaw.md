# OpenClaw Pattern Extraction Plan for NEQ OpenRouter + EGO

Status: Planning artifact (pre-OpenSpec)
Owner: NEQ core maintainers
Date: 2026-02-18
Scope: Extract high-value architecture patterns from OpenClaw for:
1) OpenRouter LLM foundation rebuild in NEQ
2) Follow-up EGO/RATIO control system build

---

## 1) Executive position

This plan does **not** adopt OpenClaw as NEQ's whole LLM brain.

Instead, it treats OpenClaw as a high-velocity reference implementation for:
- provider failover discipline,
- auth/profile lifecycle management,
- model operations UX,
- idempotent request contracts,
- and runtime observability.

NEQ keeps its current architectural doctrine:
- Python is mechanical ground truth.
- LLM is interpretation and generation layer.
- Combat/mechanics remain deterministic and fail-safe.

---

## 2) Why this matters now

NEQ already has the right direction in flight:
- `plans/openrouter_llm_router_architecture.md`
- `plans/EGO.md`

What this document adds is a "fine-toothed comb" pass over battle-tested patterns from OpenClaw, mapped directly into NEQ implementation sequencing so we avoid both:
- overbuilding a generic gateway system,
- and underbuilding core reliability controls.

---

## 3) Source basis (OpenClaw examples)

### Product and architecture context
- OpenClaw repo root: https://github.com/openclaw/openclaw
- README: https://github.com/openclaw/openclaw/blob/main/README.md
- Gateway architecture: https://github.com/openclaw/openclaw/blob/main/docs/concepts/architecture.md
- Agent loop lifecycle: https://github.com/openclaw/openclaw/blob/main/docs/concepts/agent-loop.md
- Gateway protocol: https://github.com/openclaw/openclaw/blob/main/docs/gateway/protocol.md

### Model and failover behavior
- Models overview: https://github.com/openclaw/openclaw/blob/main/docs/concepts/models.md
- Model providers: https://github.com/openclaw/openclaw/blob/main/docs/concepts/model-providers.md
- Model failover: https://github.com/openclaw/openclaw/blob/main/docs/concepts/model-failover.md

### Concrete implementation files used for extraction
- Auth profile ordering: https://github.com/openclaw/openclaw/blob/main/src/agents/auth-profiles/order.ts
- Auth profile cooldown/disable usage: https://github.com/openclaw/openclaw/blob/main/src/agents/auth-profiles/usage.ts
- Session profile override and stickiness: https://github.com/openclaw/openclaw/blob/main/src/agents/auth-profiles/session-override.ts
- Auth health summary: https://github.com/openclaw/openclaw/blob/main/src/agents/auth-health.ts
- Models fallback command helpers: https://github.com/openclaw/openclaw/blob/main/src/commands/models/fallbacks-shared.ts
- Models status command: https://github.com/openclaw/openclaw/blob/main/src/commands/models/list.status-command.ts
- Models scan command: https://github.com/openclaw/openclaw/blob/main/src/commands/models/scan.ts
- Protocol schema registry: https://github.com/openclaw/openclaw/blob/main/src/gateway/protocol/schema.ts
- Protocol frame schema: https://github.com/openclaw/openclaw/blob/main/src/gateway/protocol/schema/frames.ts
- Agent/request schemas with idempotency keys: https://github.com/openclaw/openclaw/blob/main/src/gateway/protocol/schema/agent.ts

---

## 4) Extracted patterns worth adopting in NEQ

### P1) Two-stage failover (profile first, model second)

OpenClaw pattern:
- Rotate through auth profiles for the same provider first.
- Escalate to model fallback only after profile exhaustion.

NEQ adaptation:
- Keep provider/model hierarchy in router, but add profile-level retries before cross-model fallback.
- This improves continuity and avoids unnecessary style/model drift.

Primary references:
- docs/concepts/model-failover.md
- src/agents/auth-profiles/order.ts
- src/agents/auth-profiles/usage.ts

### P2) Explicit failure taxonomy and cooldown state machine

OpenClaw pattern:
- Failure reasons split (billing vs transient/unknown).
- Distinct cooldown vs disabled windows.
- Exponential backoff and expiry clearing.

NEQ adaptation:
- Add deterministic error classes: `auth`, `rate_limit`, `timeout`, `billing`, `invalid_request`, `transient`, `fatal`.
- Apply class-specific routing decisions.

Primary references:
- src/agents/auth-profiles/usage.ts
- docs/concepts/model-failover.md

### P3) Session stickiness with controlled rotation

OpenClaw pattern:
- Session can pin profile; rotate on compaction/new-session or cooldown.

NEQ adaptation:
- Session-level profile stickiness per campaign/session key.
- Rotate only when failure or explicit reset conditions are hit.

Primary references:
- src/agents/auth-profiles/session-override.ts
- docs/concepts/model-failover.md

### P4) Operator-grade model diagnostics

OpenClaw pattern:
- `models status` and `models scan` provide practical run-state and provider health insight.

NEQ adaptation:
- Add lightweight NEQ commands/scripts for router status, fallback chain, and auth health.

Primary references:
- src/commands/models/list.status-command.ts
- src/commands/models/scan.ts
- docs/concepts/models.md

### P5) Idempotency on side-effecting requests

OpenClaw pattern:
- Protocol-level `idempotencyKey` in side-effect methods.

NEQ adaptation:
- Add idempotency keys to write-producing AI actions and wrapper operations to prevent duplicate writes on retries.

Primary references:
- src/gateway/protocol/schema/agent.ts
- docs/gateway/protocol.md

### P6) Structured lifecycle envelopes

OpenClaw pattern:
- Agent loop emits lifecycle and stream semantics (`runId`, start/end/error).

NEQ adaptation:
- Every LLM call in router emits a stable envelope for observability and EGO ingestion.

Primary references:
- docs/concepts/agent-loop.md
- docs/gateway/protocol.md

### P7) Health summaries as first-class objects

OpenClaw pattern:
- Build auth provider/profile health summary with expiring/expired/missing states.

NEQ adaptation:
- Build `router_health` snapshots and expose them in CLI/debug routes.

Primary references:
- src/agents/auth-health.ts
- src/commands/models/list.status-command.ts

---

## 5) Explicit non-goals (what we do NOT adopt)

1. No Gateway daemon architecture for core NEQ LLM path.
2. No channel/message-bus control plane as a prerequisite for game runtime.
3. No broad tool runtime or node pairing model.
4. No replacement of NEQ Python-first orchestration with Node-side orchestration.

Reason:
- NEQ must stay deterministic in mechanics and locally operable for tabletop facilitators.

---

## 6) Integration plan A: OpenRouter foundation rebuild

This section is implementation-oriented and intended to directly inform work after current stabilization.

### A0) Baseline alignment and terminology lock

Objectives:
- Freeze terms and behavior contracts before coding.

Actions:
1. Define router error classes and fallback transitions in one docstring/spec block.
2. Define "session" identity used for stickiness (campaign + channel + active PC context where relevant).
3. Confirm which NEQ call sites are "mechanics-critical" vs "narrative-flexible".

NEQ files to update:
- `utils/ai_client_factory.py` (doc block)
- `model_config.py` (error/fallback config constants)

Acceptance:
- One canonical error taxonomy and transition matrix checked into code comments.

---

### A1) Router call envelope and telemetry contract

Objectives:
- Introduce a uniform envelope for all LLM calls.

Proposed envelope fields:
- `run_id`
- `task`
- `provider_requested`, `provider_used`
- `model_requested`, `model_used`
- `profile_used`
- `started_at`, `ended_at`, `latency_ms`
- `attempt_count`
- `fallback_chain`
- `error_class` (if any)
- `success`

Implementation targets:
- `utils/llm_router.py` (new or expanded)
- `utils/ai_client_factory.py` (adapter support)
- `core/managers/status_manager.py` (optional user-facing status)

OpenClaw basis:
- docs/concepts/agent-loop.md
- docs/gateway/protocol.md

Acceptance:
- 100 percent of router-invoked calls return/store the envelope.

---

### A2) Profile store and cooldown engine

Objectives:
- Add provider profile lifecycle state and backoff logic.

Design notes:
- Keep store format simple JSON in NEQ data path.
- Thread-safe access (lock file or process-local mutex + atomic write).
- Separate `cooldown_until` from `disabled_until` (billing).

Implementation targets:
- `utils/llm_profile_store.py` (new)
- `utils/llm_router.py` (integration)
- `model_config.py` (configurable cooldown windows)

OpenClaw basis:
- src/agents/auth-profiles/usage.ts
- src/agents/auth-profiles/order.ts

Acceptance:
- Simulated failure tests prove profile rotation and cooldown expiry behavior.

---

### A3) Session stickiness and controlled rotation

Objectives:
- Maintain model/profile continuity per gameplay session.

Design notes:
- Stickiness key should not be global; use scoped key to avoid cross-campaign bleed.
- Rotation triggers:
  - explicit reset,
  - cooldown/disable of active profile,
  - fatal provider error.

Implementation targets:
- `utils/llm_router.py`
- optional metadata in existing session/campaign tracking layer

OpenClaw basis:
- src/agents/auth-profiles/session-override.ts

Acceptance:
- Same session uses same profile under normal conditions.
- Failure rotates profile deterministically.

---

### A4) Error-class-aware fallback matrix

Objectives:
- Make fallback decisions deterministic and testable.

Proposed matrix (initial):
- `rate_limit`, `timeout`, `transient` -> profile rotate, then model fallback
- `billing` -> disable profile, skip until expiry, then fallback
- `auth` -> immediate profile skip for provider
- `invalid_request` -> fail-fast unless known-safe transform path exists
- `fatal` -> fail-fast

Implementation targets:
- `utils/llm_router.py`
- `utils/ai_client_factory.py`

OpenClaw basis:
- docs/concepts/model-failover.md
- src/agents/auth-profiles/usage.ts

Acceptance:
- Unit tests cover each error class and expected next state.

---

### A5) Idempotency for write-side actions

Objectives:
- Prevent duplicate game-state writes from retry loops.

Design notes:
- Generate deterministic `idempotency_key` at action boundary.
- Store short-lived key ledger for write actions.
- If key already consumed, return prior result instead of re-applying.

Implementation targets:
- `core/ai/action_handler.py`
- `updates/update_character_info.py`
- `updates/update_encounter.py`
- supporting utility module `utils/idempotency.py` (new)

OpenClaw basis:
- src/gateway/protocol/schema/agent.ts

Acceptance:
- Retry simulation does not duplicate HP, encounter, or plot writes.

---

### A6) Router diagnostics and operator commands

Objectives:
- Provide practical visibility and troubleshooting hooks.

Deliverables:
1. `python scripts/router_status.py`:
   - active provider/model/profile
   - fallback chain
   - cooldown/disabled profile summary
   - recent error classes
2. `python scripts/router_probe.py` (optional):
   - quick provider reachability probe
   - latency sample

OpenClaw basis:
- src/commands/models/list.status-command.ts
- src/commands/models/scan.ts

Acceptance:
- Live tabletop operator can identify router health in <30 seconds.

---

### A7) Testing strategy and quality gates

Objectives:
- Ensure router reliability before full migration.

Test layers:
1. Unit tests: classification, cooldown math, order resolution.
2. Integration tests: simulated provider failures and fallback.
3. Regression tests: combat and non-combat smoke with fallback induced.

Suggested new tests:
- `scripts/test_llm_router_failover.py`
- `scripts/test_llm_router_stickiness.py`
- `scripts/test_llm_router_idempotency.py`

Acceptance gates:
- No deterministic behavior regressions in combat validation.
- Failures degrade gracefully with no duplicate writes.

---

## 7) Integration plan B: EGO follow-on (after router hardening)

EGO should consume router telemetry, not re-invent it.

### B0) Hard prerequisite checklist

Must be true before EGO active adaptation:
1. Router envelopes are complete and stable.
2. Error taxonomy is deployed and tested.
3. Idempotency guard is in place for write actions.
4. Router health command is available.

---

### B1) Passive observer phase

Objectives:
- Ingest router envelopes and gameplay outcomes without making prompt writes.

Data to collect:
- run latency by task
- fallback frequency by task
- error class by provider/model/profile
- retries per call
- mechanical correction events after model output

Implementation targets:
- existing memory infrastructure in `core/memory/`
- optional dedicated tables for `llm_run_log` and `llm_run_aggregates`

OpenClaw basis:
- docs/concepts/agent-loop.md
- src/agents/auth-health.ts

Acceptance:
- Can produce session report identifying high-friction tasks and unstable providers.

---

### B2) EGO classification enhancement

Objectives:
- Extend DRIFT/DISTORTION/HALLUCINATION logic with router telemetry context.

Examples:
- High hallucination + high fallback rate on same task -> profile/model routing candidate.
- Distortion spikes only after specific provider fallback -> provider-specific guardrail proposal.

Implementation targets:
- `core/managers/world_observer.py` (or equivalent observer)
- EGO analysis modules (future)

Acceptance:
- EGO outputs include both narrative divergence and router condition context.

---

### B3) Bounded EGO adjustments (Tier 1a only)

Objectives:
- Allow small tactical changes under strict safety budget.

Examples:
- task-specific temperature clamps,
- stricter JSON instruction templates for unstable tasks,
- temporary provider preference for a task under incident mode.

Safety rules:
- cooldown between adjustments,
- max N adjustments per session,
- automatic rollback trigger on regression signal.

OpenClaw basis:
- model failover and health-state ideas, not direct code architecture.

Acceptance:
- No mechanics regressions while reducing correction burden.

---

### B4) RATIO proposal phase

Objectives:
- Use accumulated telemetry to propose medium-horizon prompt/routing improvements.

Inputs:
- EGO escalations,
- router fallback and error histograms,
- task-specific latency/cost patterns.

Outputs:
- reviewable proposal bundle with before/after predictions,
- reversible patch set,
- replay/regression checklist.

Acceptance:
- Human-reviewed proposals demonstrate net quality gain over baseline windows.

---

## 8) Unified contract proposals (for implementation)

### 8.1 Router run record (example)

```json
{
  "run_id": "llm_20260218_123456_ab12",
  "task": "combat_validate",
  "provider_requested": "openrouter",
  "provider_used": "openrouter",
  "model_requested": "google/gemini-2.5-flash-lite",
  "model_used": "google/gemini-2.5-flash-lite",
  "profile_used": "openrouter:default",
  "attempt_count": 2,
  "fallback_chain": [
    "profile:openrouter:default",
    "profile:openrouter:secondary"
  ],
  "error_class": null,
  "started_at": "2026-02-18T12:34:56Z",
  "ended_at": "2026-02-18T12:34:57Z",
  "latency_ms": 943,
  "success": true
}
```

### 8.2 Profile usage state (example)

```json
{
  "profiles": {
    "openrouter:default": {
      "last_used": 1770000000000,
      "error_count": 0,
      "cooldown_until": null,
      "disabled_until": null,
      "disabled_reason": null
    }
  }
}
```

### 8.3 EGO ingestion fields (minimum)

- `run_id`
- `task`
- `latency_ms`
- `attempt_count`
- `fallback_used` (bool)
- `error_class`
- `post_action_mechanical_correction` (bool)

---

## 9) Fine-toothed comb checklist

Use this as an execution checklist while coding.

1. Do all LLM paths produce a run envelope?
2. Are error classes deterministic and unit-tested?
3. Is cooldown vs disable behavior separate and observable?
4. Is session stickiness scoped correctly (no cross-session bleed)?
5. Are write-side retries idempotent?
6. Are combat-critical tasks protected with stricter fail-fast behavior?
7. Can operator inspect active profile/model and recent fallback reasons quickly?
8. Are EGO features reading router telemetry instead of re-deriving it?
9. Is every adaptation reversible with clear rollback path?
10. Are SP and tabletop multiplayer both covered in regression tests?

---

## 10) Risks and mitigations

### Risk R1: Over-complexity from copying too much platform behavior
Mitigation:
- Adopt only router/failover/health patterns, not gateway architecture.

### Risk R2: Retry loops cause duplicate mechanical writes
Mitigation:
- Idempotency keys and write-ledger checks before action apply.

### Risk R3: Profile rotation harms narrative continuity
Mitigation:
- Session stickiness first; rotate only under explicit failure conditions.

### Risk R4: EGO tunes around provider incidents instead of root causes
Mitigation:
- Include router condition context in every escalation and review bundle.

### Risk R5: Observability overhead affects gameplay latency
Mitigation:
- Keep telemetry writes lightweight and optionally batch async where safe.

---

## 11) Recommended execution order (practical)

1. A1 Router envelope
2. A2 Cooldown/disable profile store
3. A4 Error-class fallback matrix
4. A3 Session stickiness
5. A5 Idempotency for write actions
6. A6 Diagnostics commands
7. A7 Test hardening
8. B1 Passive EGO ingestion
9. B2-B4 staged EGO/RATIO enablement

This order gives immediate reliability gains before adaptive systems are turned on.

---

## 12) Bottom line

OpenClaw should be treated as a pattern library, not a runtime dependency for NEQ core mechanics.

The strongest transfer value is:
- failover rigor,
- profile lifecycle controls,
- idempotency discipline,
- and operational diagnostics.

Those patterns materially strengthen both NEQ's OpenRouter rebuild and the safety envelope for later EGO/RATIO work.

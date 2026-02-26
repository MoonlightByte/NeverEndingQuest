# EGO + RATIO Concept Plan (Draft)

## Status

- This document is conceptual review only.
- It is not an implementation commitment.
- It defines a possible future build after current stabilization work.

## Titan v2 Alignment Stub

- Umbrella reference: `plans/version-2/titan-integration.md`
- Retune status: Pending (not yet rewritten to Titan cycle architecture)
- Last tagged: 2026-02-26
- Retune focus: Titan identity scheduler, interpreted-only writes, and proposal/apply boundaries

## Purpose

Define a bounded cybernetic control architecture for narrative quality in NeverEndingQuest.

Core intent:
- Keep Python mechanics as non-negotiable ground truth.
- Detect and reduce narrative-mechanical divergence.
- Improve prompt behavior over time without touching game state.

## Terminology

- EGO: Evaluator/Guardian Observer
  - Fast triage loop.
  - Works on live event streams.
  - Writes only safe tuning knobs.

- RATIO: Rational Adjustment and Tuning Orchestrator
  - Slower between-session optimizer.
  - Proposes and applies broader prompt edits behind review gates.

- World-Brain
  - SQLite authority for surveillance, prompt surfaces, and evolution history.
  - Runtime implementation should align with `data/memory.db` narrative tables.
  - Optional compatibility layer/view may be named "world_brain" without separate raw-source storage.

## Copyright and Upload Boundary (Sync Requirement)

This EGO/RATIO plan must remain aligned with world-narrative copyright policy:

1. Raw uploaded books/files are local-only under `/user_uploads/text/` (gitignored).
2. EGO and RATIO never read raw source files directly in normal operation.
3. EGO/RATIO consume only source-anonymous atoms and interpreted world model state.
4. No title/author/source metadata is stored in committable DB rows used by EGO/RATIO.
5. Tester distributions may include baseline source-anonymous seed DB only, never local uploads.

## Prerequisite

This plan depends on completion of the OpenRouter router facade work:

- `plans/version-2/openrouter_llm_router_architecture.md`

Required capability:
- Unified `llm.call(task=...)` entrypoint with role/task routing, usage stats, and fallback.

Without router completion:
- EGO Phase 1 (passive recording only) is possible.
- EGO analysis and all RATIO model-driven synthesis should be deferred.

## Boundary Contract (Non-Negotiable)

1. Python engine state is authoritative.
2. EGO and RATIO never write character/encounter/party mechanical state.
3. EGO writes only Tier 1a prompt knobs.
4. RATIO writes only Tier 1a, 1b, and 2 prompt surfaces.
5. Tier 3 prompt contracts are immutable.
6. All prompt edits are logged, attributable, and reversible.

## Why Two Systems

Single-loop systems either become too weak (no adaptation) or too risky (unchecked edits).

Split loops provide control separation:

- EGO (fast, bounded):
  - Detects divergence per turn.
  - Performs low-risk corrective tuning.
  - Escalates unresolved patterns.

- RATIO (slow, reflective):
  - Learns from escalation clusters.
  - Proposes structural prompt changes.
  - Uses review gate + regression checks before deployment.

## Reality Model

Track A: Mechanical Reality
- Source: Python game state transitions.
- Property: causal and deterministic within game rules.

Track B: Narrative Reality
- Source: LLM emitted narration.
- Property: interpretive and stylistic.

Control objective:
- Maximize narrative richness while keeping consistency with Track A.

## Decision Relay (EGO)

Each analyzed divergence receives one outcome:

- END (DRIFT)
  - Divergence is acceptable flavor.
  - Record and continue.

- ADJUST (DISTORTION)
  - Recoverable mismatch.
  - Apply bounded Tier 1a adjustment.

- ESCALATE (HALLUCINATION)
  - Serious causal break.
  - Inject correction guidance for next turn.
  - Queue for RATIO and coder review.

## World-Brain Layers (Proposed)

Layer 1: Event ledger
- Mechanical and narrative event records.

Layer 2: Surveillance
- EGO reports with severity/domain and correction vectors.

Layer 3: Prompt authority
- Prompt files, directives, parameters, sections, history.

Layer 4: Evolution
- RATIO proposals, reviews, deployment outcomes, pattern library.

Layer 5: Coder review queue
- Human/agent reviewable diffs and decisions.

## Write Surface Policy

Tier 1a (EGO + RATIO)
- Small bounded knobs:
  - selected temperatures,
  - narration quotas,
  - limited style weights.

Tier 1b (RATIO only)
- Safe prose-level guidance and examples.

Tier 2 (RATIO only + stronger checks)
- Behavioral guidance that can shift outcomes but should not break parsers.

Tier 3 (immutable)
- Output schemas,
- action contracts,
- parser-critical and validation-critical directives.

## Human DM as External Input

Human behavior is an exogenous control signal, not noise.

Implication:
- The system should distinguish unsanctioned hallucination from table-preferred style drift.

Design note:
- "Silence means approval" is useful but weak by itself.
- Use multiple signals before treating divergence as sanctioned:
  - no correction request,
  - no regenerate/edit,
  - stable continuation over subsequent turns.

## Observability and Safety Requirements

Required before any autonomous adjustment:

1. End-to-end event traceability
2. Session-level and parameter-level rollback
3. Adjustment budgets and cooldowns
4. Clear error classification
5. Alerting for repeated escalations
6. Replay/regression harness for prompt edits

Operational limits:
- Max adjustments per session
- Per-parameter cooldown window
- Escalation thresholds per domain

## Integration Points (Current Codebase)

Likely anchor points already present:

- `core/managers/world_observer.py`
- `web/web_interface.py` live narrative emit path
- `updates/update_character_info.py`
- `core/managers/combat_manager.py`
- `core/ai/action_handler.py`
- `updates/update_encounter.py`

The initial plan should prefer additive hooks and preserve upstream merge safety markers.

## Implementation Phasing (Conceptual)

Phase 0: Gate conditions
- Router facade available and stable.
- Current production build stabilized.
- Baseline metrics captured.

Phase 1: Passive foundation
- Event capture and surveillance storage only.
- No prompt writes.
- Prompt import tooling validated against source files.

Phase 2: EGO observe and classify
- DRIFT/DISTORTION/HALLUCINATION classification.
- Dashboard and audit quality measurement.
- Still no live writes by default.

Phase 3: Bounded EGO adjustments
- Enable Tier 1a writes in canary mode.
- One or two knobs max at first.
- Hard rollback + cooldown enabled.

Phase 4: RATIO proposal engine
- Between-session synthesis of recurring escalations.
- Review gate required for deployment.

Phase 5: Controlled adaptation
- Pattern library,
- measured pre/post outcomes,
- optional limited auto-deploy for low-risk edits only.

## Suggested Go/No-Go Gates

Do not advance a phase unless prior gate passes.

Gate A (after Phase 1):
- Event coverage complete for critical domains.
- Prompt import/build round-trip validated.

Gate B (after Phase 2):
- Classification quality acceptable.
- No latency impact on gameplay loop.

Gate C (after Phase 3):
- No oscillation across canary sessions.
- Adjustment rollback proven.

Gate D (after Phase 4):
- Review process throughput acceptable.
- Proposed edits show net positive effect.

## Major Risks

1. Overfitting to short-term play style
2. Controller oscillation from aggressive auto-tuning
3. Prompt regression from broad structural edits
4. Prompt authority migration fragility (DB as runtime source)
5. Excess cost from over-frequent analysis calls

## Mitigations

- Strict tier enforcement
- Write budgets + cooldowns
- Human/agent review queue
- Regression replay before deploy
- Last-good prompt fallback
- Conservative canary rollout

## Success Criteria (Conceptual)

System quality:
- Fewer severe narrative-mechanical contradictions over time.
- No increase in parser/contract failures.
- No degradation of table-level enjoyment signals.

Control quality:
- Escalation rates trend down for repeated domains.
- Adjustments are explainable and reversible.
- Cost overhead remains bounded and predictable.

## Out of Scope (for this plan stage)

- Code-writing autonomy by RATIO.
- Direct modification of gameplay mechanics.
- Any bypass of Tier 3 constraints.
- Replacing human/agent governance for high-risk edits.

## Recommended Next Step

Treat this as architecture intent and convert it into a short OpenSpec change set after current build release:

1. `ego-foundation-passive-observer`
2. `ego-bounded-adjustments`
3. `ratio-reviewed-evolution`

Each should include explicit rollback and go/no-go criteria.

## OpenSpec Scaffolding Map

This section maps the concept plan into future OpenSpec changes so work can start quickly later.

Current relevant OpenSpec groundwork already present:
- `openspec/changes/openrouter-llm-router-facade`
- `openspec/changes/openrouter-llm-callsite-migration`

Proposed future OpenSpec changes for EGO/RATIO:

1. `ego-foundation-passive-observer`
   - Scope: world-brain schema, event ingestion, passive surveillance writes, no prompt writes.
   - Must prove: event coverage and prompt import/build round-trip.

2. `ego-bounded-adjustments`
   - Scope: EGO classification and Tier 1a canary adjustments with hard rollback.
   - Must prove: no oscillation, bounded adjustment count, stable latency.

3. `ratio-reviewed-evolution`
   - Scope: between-session synthesis, review gate, deployment history, regression replay.
   - Must prove: net positive edits and safe rollback path.

Suggested command sequence when ready:

```bash
openspec new change ego-foundation-passive-observer --description "Phase 1 passive EGO foundation"
openspec new change ego-bounded-adjustments --description "Phase 2 bounded Tier 1a EGO adjustments"
openspec new change ratio-reviewed-evolution --description "Phase 3 RATIO reviewed prompt evolution"
```

Then for each change:

```bash
openspec status --change "<change-name>" --json
openspec instructions continue --change "<change-name>" --json
openspec instructions apply --change "<change-name>" --json
```

## OpenSpec Artifact Checklist (Per Change)

Proposal must include:
- explicit non-goals
- rollback trigger conditions
- cost and latency budget assumptions

Design must include:
- data-flow boundaries (Python truth vs prompt surfaces)
- tier enforcement strategy
- failure and recovery paths

Specs must include:
- testable invariants for write boundaries
- acceptance criteria for phase gate
- no-regression criteria for SP/MP behavior

Tasks must include:
- concrete file targets
- verification command per task
- halt conditions that block phase advancement

## Suggested Scope Boundaries for Early Execution

To avoid overreach during initial implementation:
- Do not combine all three EGO/RATIO changes into one OpenSpec change.
- Do not enable live prompt writes in the same change that introduces new event pipes.
- Do not enable RATIO auto-deploy before replay/regression tooling exists.
- Keep coder review queue mandatory for medium/high-risk edits.

## Definition of Ready (Before Starting EGO OpenSpec Work)

All of the following should be true:
1. Current tester build is stabilized and released.
2. OpenRouter router-facade change is implemented and validated.
3. OpenRouter callsite migration change is implemented and validated.
4. Baseline divergence metrics are captured from live sessions.
5. Time budget and cost budget for EGO canary sessions are defined.

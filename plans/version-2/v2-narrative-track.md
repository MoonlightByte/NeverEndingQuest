# V2 Narrative Track (Cohesion Spine)

Status: Working architecture track (in progress)
Date: 2026-03-09
Owner: NEQ v2 narrative architecture

## Purpose

Provide one execution spine across v2 planning docs so continuity, world narrative, memory, EGO, and Titan work advance in a single ordered track with shared vocabulary.

This document is planning-level only. It intentionally does not replace implementation specs.

## Shared Terms (Canonical)

- `continuity_contract`: Module-level continuity payload emitted by ingest.
- strict mode: missing required continuity keys fail closed.
- warn-first mode: soft continuity issues are warnings and do not block publish.
- interpreted state: narrative pressure/state that never mutates mechanical truth.
- mechanical truth: Python-enforced gameplay state.
- proposal/apply lifecycle: interpreted world updates are proposed, reviewed, then applied.

## Current Baseline (Implemented)

The initial continuity substrate is operational:

1. Ingest emits and persists `continuity_contract`.
2. Sidecar audit validates continuity payload shape.
3. Readiness gate includes continuity checks.
4. Bulk validation reports continuity outcomes, including summary counts.

Required continuity keys in v1 baseline:
- `continuity_version`
- `entry_state_variants`
- `cross_module_refs`
- `standalone_fallback`

## V2 Phase Map

Phase 1: Continuity Substrate (DONE)
- Scope: ingest/readiness/sidecar/bulk continuity contracts.
- Outcome: deterministic module continuity gate now exists.

Phase 2: World Model and Memory Lift (IN PROGRESS)
- Scope: map module continuity signals into world narrative interpretation inputs.
- Outcome target: continuity-aware world model proposals without mechanical writes.

Phase 3: EGO and Titan Runtime Bridge (PLANNED)
- Scope: consume continuity and interpreted world signals in Titan/EGO cycles.
- Outcome target: proposal-only world pressure updates with fail-open runtime behavior.

Phase 4: Builder and Module Feedback Loop (PLANNED)
- Scope: module builder consumes approved pressure and writes provenance-safe continuity seeds.
- Outcome target: ongoing LLM-assisted world-building loop with review boundaries.

Phase 5: Governance and Observability Hardening (PLANNED)
- Scope: policy gates, auditability, rollback, cost/latency envelopes.
- Outcome target: safe long-horizon adaptation pipeline.

## Plan Ownership Matrix

- `plans/ingest-module.md`
  - Owns: ingest/watcher operational flow and continuity payload emission behavior.
- `plans/version-2/module-import.md`
  - Owns: high-volume import pipeline and any-order readiness policy.
- `plans/version-2/world-narrative.md`
  - Owns: interpreted world model architecture and copyright-safe narrative store.
- `plans/version-2/memory.md`
  - Owns: retrieval/storage contracts and memory-layer integration with continuity quality signals.
- `plans/version-2/CNS build/EGO.md`
  - Owns: bounded adaptive control architecture and write-surface policy.
- `plans/version-2/titan-integration.md`
  - Owns: umbrella runtime integration design for Titan cycle architecture.
- `plans/version-2/titan-retune-execution-order.md`
  - Owns: implementation sequencing, dependency ordering, and retune gates.

## Dependency Chain

1. Continuity substrate (already done) ->
2. world-narrative + memory interpreted contracts ->
3. EGO/Titan runtime bridge ->
4. module-builder continuity pressure integration ->
5. governance hardening.

## Next Milestone

Backfill continuity keys across active modules and move continuity gate outcomes from mostly-fail to mostly-pass in strict mode for release-target modules.

## Exit Criteria

This narrative track is considered cohesive when:

1. All listed plans reference this spine and use shared terms.
2. No plan contradicts strict/warn continuity behavior.
3. No plan allows interpreted layers to bypass Python mechanical truth.
4. Titan/EGO phases explicitly consume continuity outputs as quality inputs.
5. Builder integration remains proposal/apply and provenance-safe.

## Working Note

OpenSpec implementation sequencing is intentionally deferred for now, per current architecture-in-progress workflow. This file is the planning alignment anchor until execution sequencing resumes.

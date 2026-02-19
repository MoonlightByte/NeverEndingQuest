# Module Builder Enhancements Roadmap

Status: Planned (foundation doc)
Owner: Toolkit rebuild workstream
Date: 2026-02-19
Scope: Multi-phase rebuild of module toolkit and module builder with Phase 1 focused on NPC generation/promotion alignment.

---

## 1) Why this roadmap exists

The current module builder can generate playable modules, and current TABLETOP MODE flows can recruit NPC allies and promote NPC -> PC in Manage Party/Add Existing.

However, NPC data quality still depends on late runtime materialization and minimal context passing. This creates avoidable drift between:
- module-authored NPC intent (location/plot context),
- generated NPC sheet quality,
- and profile readiness for portrait/promotion paths.

This roadmap formalizes a safe, phased rebuild so we can improve quality without destabilizing gameplay.

---

## 2) Current gameplay impact assessment

### Current viability
- Enlisting NPC allies in active campaigns is expected to work via `updatePartyNPCs` -> `npc_builder.py` runtime creation.
- NPC -> PC switching in Manage Party/Add Existing is expected to work with the current promotion preview/apply routes.

### Known current risks (quality/reliability, not hard blockers)
- Runtime-created NPC files can be generic if module context is not passed.
- Name variance and fuzzy matching can still produce occasional duplicate/near-duplicate NPC files.
- Provider/runtime failure in NPC generation can degrade enlist flow if fallback data is sparse.

### Recommendation
- Do not block current campaigns on this work.
- Implement as Phase 1 of a broader toolkit rebuild.

---

## 3) Rebuild principles

1. Preserve current gameplay contracts first.
2. Prefer additive architecture and merge-safe host edits (`# TABLETOP MODE:`).
3. Improve deterministic data contracts before UI polish.
4. Keep lazy runtime materialization unless there is a measured need for eager generation.
5. Preserve SP and TABLETOP MODE compatibility.

---

## 4) Phased roadmap

## Phase 0: Baseline and instrumentation (pre-work)

Objective: establish observability and test safety before behavioral changes.

Deliverables:
- Baseline tests for module generation, enlist, and NPC -> PC promotion.
- Simple telemetry/log markers for NPC materialization source and fallback path.
- Error taxonomy for NPC generation failures.

Exit criteria:
- Repeatable baseline test pass in local environment.
- No unknown error classes in the first telemetry pass.

---

## Phase 1: NPC alignment foundation (initial implementation phase)

Objective: align module-authored NPC intent with runtime NPC sheet materialization and promotion readiness.

Core outcomes:
1. Generate per-module NPC profile seeds (`npc_profile_seeds.json`).
2. Upgrade `npc_builder` to consume seed context and enforce deterministic postprocessing.
3. Pass module seed context from enlist/combat NPC materialization callsites.
4. Harden Add Existing candidate classification so NPC files are not surfaced as players.

Constraints:
- Keep lazy materialization (do not generate full sheets for all module NPCs at build time).
- Preserve current enlist and promotion UX/behavior.

Exit criteria:
- New module -> recruit NPC ally -> promote NPC -> all succeed.
- Generated NPC files are role-normalized and profile-field-ready.
- Regression tests for seed contract and runtime callsite alignment pass.

---

## Phase 2: Module authoring quality controls

Objective: improve first-pass module output consistency and lower NPC/plot cleanup overhead.

Candidate scope:
- Stronger location/NPC consistency prompts.
- Better canonicalization hooks in module context/reconciler.
- Deterministic post-generation validation and targeted fix-up passes.

Exit criteria:
- Reduced duplicate NPC canonicalization events.
- Fewer post-generation corrections needed in smoke runs.

---

## Phase 3: Toolkit generation orchestration hardening

Objective: make long-running toolkit generation robust and recoverable.

Candidate scope:
- Better job/state tracking for build progress and cancellation.
- Retry/backoff policy for provider calls by operation type.
- Partial-failure reporting and resumable checkpoints.

Exit criteria:
- Controlled behavior under provider latency/failure.
- No silent partial generation failures.

---

## Phase 4: Builder UX and operator controls

Objective: improve facilitator/operator confidence without changing game rules.

Candidate scope:
- Clear preflight checks and warnings.
- Better progress detail and actionable error messages.
- Optional post-build quality report in toolkit UI.

Exit criteria:
- End-to-end builder flow understandable without log spelunking.
- Fewer manual retries due to unknown failure causes.

---

## Phase 5: Optional architecture convergence

Objective: evaluate deeper unification with future toolkit and storage direction.

Candidate scope:
- Evaluate abstraction-first storage path for generated character artifacts.
- Optional provider-routing consolidation for generation paths.
- Optional eager materialization mode behind explicit operator flag.

Exit criteria:
- Decision record for long-term architecture direction.
- No regressions to current campaign playability.

---

## 5) Phase 1 implementation focus summary

Phase 1 is intentionally narrow:
- It improves NPC data contracts and runtime alignment.
- It does not require immediate gameplay migration.
- It provides the most value-to-risk ratio before broader rebuild steps.

---

## 6) Verification strategy for this roadmap

For each phase:
1. Compile checks for changed Python files.
2. Targeted regression tests for touched flows.
3. One manual smoke for primary facilitator workflow.
4. Fail-open behavior confirmed for non-critical enhancement paths.

---

## 7) OpenSpec link

Initial OpenSpec scaffold for Phase 1 is tracked in:
- `openspec/changes/toolkit-module-builder-rebuild-phase1-npc-alignment/`

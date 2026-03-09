# Titan v2 Retune Execution Order

Status: Planning in progress (v2 kickoff checklist)
Date: 2026-02-26
Owner: NEQ v2 rebuild sequencing
Primary reference: `plans/version-2/titan-integration.md`
Track reference: `plans/version-2/v2-narrative-track.md`

---

## 1) Purpose

This document is the practical start-order checklist for retuning existing NEQ plans and OpenSpec drafts to the Titan v2 architecture.

Use this when v1 testing is complete and v2 implementation begins.

## Current Baseline

The following substrate is now already in place before Titan retune starts:

1. Ingest continuity contract emission (`continuity_contract`).
2. Sidecar continuity payload validation.
3. Readiness continuity gate and strict/warn mode support.
4. Bulk validator continuity reporting (including summary counts).

Retune implication:
- Phase 0 and Phase 3 should treat module continuity gating as existing infrastructure, then extend upward into Titan relationship/cycle layers.

## Next Milestone

Apply this baseline explicitly in Phase 0 acceptance and Phase 3 schema retune tasks so Titan planning starts from continuity-aware contracts.

## Exit Criteria

- Phase checklist explicitly references continuity substrate dependencies.
- Titan retune phases do not duplicate already-implemented continuity gate work.
- Retune sequence preserves strict/warn continuity semantics end-to-end.

---

## 2) Scope

Included:

- plan retuning
- OpenSpec retuning
- execution sequencing and gate criteria
- dependency order across OpenRouter, EGO, world-narrative, module builder, and seeding

Excluded:

- direct code implementation tasks
- migration scripts and PR-level work breakdown

---

## 3) Priority rules

1. Preserve truth hierarchy first (mechanics in Python, narrative pressure in Titan/EGO).
2. Build interfaces before behavior (contracts before generation).
3. Keep gameplay fail-open for all Titan background failures.
4. Never allow Titan output to bypass declaration gates for monsters/NPCs.
5. Gate all apply logic behind proposal lifecycle and provenance.

---

## 4) Ordered retune phases

## Phase 0 - Kickoff lock

Goal: freeze scope and lock the umbrella contract before editing sub-plans.

Checklist:

- [ ] Confirm `plans/version-2/titan-integration.md` is accepted as v2 umbrella contract.
- [ ] Confirm v2 non-negotiables remain unchanged (no mechanics writes by Titan).
- [ ] Confirm Titan IDs and naming are final: `L-`, `C-`, `N-order`, `-G`, `-E`, `-N-fate`.
- [ ] Confirm OpenRouter free-thinking policy for Titan worker default mode.

Exit gate:

- one signed-off umbrella baseline document

---

## Phase 1 - Router and callsite retune (highest dependency)

Goal: ensure model routing architecture can safely host Titan background calls.

Targets:

- `plans/version-2/openrouter_llm_router_architecture.md`
- `openspec/changes/openrouter-llm-router-facade/proposal.md`
- `openspec/changes/openrouter-llm-callsite-migration/proposal.md`

Checklist:

- [ ] Add dedicated Titan task profile and config envelope.
- [ ] Add free-tier routing policy and fallback mode (`none` default).
- [ ] Add non-blocking error contract for background cycles.
- [ ] Add usage accounting split (Titan calls vs gameplay calls).
- [ ] Add timeout and budget guardrails specific to Titan worker.

Exit gate:

- router/callsite docs can describe Titan worker call semantics without ambiguity

---

## Phase 2 - EGO retune

Goal: reshape EGO plan so Titan cycle is first-class in the fast loop.

Target:

- `plans/version-2/CNS build/EGO.md`

Checklist:

- [ ] Add `TitanCycleWorker` scheduler contract (10 min, non-overlap, lifecycle hooks).
- [ ] Add Titan selection policy (random + deterministic seed mode for tests).
- [ ] Add strict JSON output envelope and discard-invalid behavior.
- [ ] Add fail-open behavior and bounded retries/backoff.
- [ ] Add proposal-only writes as default for first rollout.
- [ ] Add review/apply gate and rollback hooks.

Exit gate:

- EGO doc can operate as the control-loop design spec for Titan cycle execution

---

## Phase 3 - World-narrative and memory schema retune

Goal: define the interpreted-state persistence and retrieval model for Titan pressure.

Targets:

- `plans/version-2/world-narrative.md`
- `plans/version-2/memory.md`
- `openspec/changes/world-narrative-seed-bootstrap-and-toolkit-ingestion/proposal.md`

Checklist:

- [ ] Add Titan-specific additive schema plan (`entity_alignment_state`, `relationship_alignment_edges`, `titan_cycle_log`, `titan_pressure_snapshots`, `world_history_lines`).
- [ ] Add relationship axis scoring and confidence/evidence requirements.
- [ ] Add proposal lifecycle states and transition rules.
- [ ] Add provenance requirements for all applied lines.
- [ ] Add retrieval ranking updates for Titan relationship analysis.
- [ ] Add data hygiene expectations for stale or low-confidence edges.

Exit gate:

- DB/storage and retrieval contract is complete for proposal/apply lifecycle

---

## Phase 4 - Module builder retune

Goal: make module generation consume approved world pressure deterministically.

Target:

- `plans/version-2/toolkit/module-builder-enhancements.md`

Checklist:

- [ ] Add approved-pressure ingestion contract.
- [ ] Add bounded influence policy (single cycle cannot dominate module output).
- [ ] Add deterministic mapping from pressure -> module hooks.
- [ ] Add provenance writeback from module output to source Titan lines.

Exit gate:

- builder plan can consume pressure signals without bypassing review/provenance rules

---

## Phase 5 - Monster/NPC seeding retune

Goal: connect Titan pressure to declarations without weakening safety controls.

Target:

- `plans/version-2/toolkit/monsters.md`

Checklist:

- [ ] Add declaration conversion step from approved Titan outputs.
- [ ] Preserve fail-closed undeclared behavior.
- [ ] Add explicit negative test case (proposal only -> no seeding).
- [ ] Add positive test case (approved declaration -> normal seeding path).
- [ ] Add provenance tags in seeding/materialization logs.

Exit gate:

- seeding plan supports Titan-derived declarations while preserving anti-hallucination guarantees

---

## Phase 6 - Mapping and observability retune

Goal: expose Titan pressure as read-only world overlays and debug views.

Target:

- `plans/version-2/world-mapping.md`

Checklist:

- [ ] Add read-only Titan pressure overlay model (world scope first).
- [ ] Add DM/debug filters by Titan/scope/status.
- [ ] Add no-data fail-open behavior for map render path.
- [ ] Add API shape for pressure overlay retrieval.

Exit gate:

- map plan can visualize pressure safely without introducing write surfaces

---

## Phase 7 - OpenSpec packaging pass

Goal: convert retuned plan state into executable OpenSpec backlog.

Checklist:

- [ ] Create/update OpenSpec changes for:
  - `titan-worker-foundation`
  - `titan-alignment-relationship-schema`
  - `titan-world-delta-proposals`
  - `titan-module-builder-pressure-integration`
  - `titan-declaration-seeding-bridge`
- [ ] Ensure each change includes non-goals, rollback triggers, and verification gates.
- [ ] Validate changes with OpenSpec validator and resolve drift.

Exit gate:

- retuned items are represented in executable OpenSpec changes with clear order

---

## 5) Quick-start checklist for first week of v2

- [ ] Day 1: complete Phase 0 and Phase 1 retune edits
- [ ] Day 2: complete Phase 2 EGO retune edits
- [ ] Day 3: complete Phase 3 schema/retrieval retune edits
- [ ] Day 4: complete Phase 4 and Phase 5 builder/seeding retune edits
- [ ] Day 5: complete Phase 6 and Phase 7 packaging edits
- [ ] End of week: review all retuned docs against `plans/version-2/titan-integration.md`

---

## 6) Dependency summary (critical path)

1. Router retune (Phase 1)
2. EGO retune (Phase 2)
3. World-narrative + memory retune (Phase 3)
4. Builder retune (Phase 4)
5. Seeding retune (Phase 5)
6. Mapping retune (Phase 6)
7. OpenSpec packaging (Phase 7)

Do not move Phase 4/5 ahead of Phase 3.
Do not move Phase 3 ahead of Phase 1/2.

---

## 7) Definition of retune completion

Retune is complete when all are true:

- [ ] all listed plan docs contain Titan-aware contracts, not just stubs
- [ ] all three OpenSpec draft proposals include Titan-aware scope statements
- [ ] dependency order and gates are explicitly documented and consistent
- [ ] no document contains Titan behavior that violates mechanics boundary
- [ ] declaration gate safety remains explicit in monsters/NPC path

---

## 8) Alpha go/no-go gate handoff

When retune work is complete, evaluate alpha readiness using the go/no-go gate in:

- `plans/version-2/titan-integration.md` -> `Alpha go/no-go gate (auto-apply enablement)`

Handoff rule:

- Do not enable Titan auto-apply during alpha until all 10 gate checks are green.
- If any check is red, keep proposal-only mode active.

Operational note:

- This document defines sequence and dependency order.
- `plans/version-2/titan-integration.md` is the authoritative gate checklist.

---

## 9) Notes for future implementation handoff

- Keep this document as sequencing guidance only.
- Implementation tasks should be tracked in OpenSpec changes, not added here.
- If architecture changes, update `plans/version-2/titan-integration.md` first, then this file.

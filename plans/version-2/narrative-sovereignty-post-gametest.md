# Narrative Sovereignty Post-Gametest Continuation

Status: Planned version-2 implementation track
Date: 2026-03-16
Owner: NEQ runtime architecture

## Purpose

Carry the deferred Lane 2 work from `plans/archive/llm-wants-to-be-free.md` into a version-2 implementation track after the gametest build is live.

This plan starts from the assumption that the G1-G4 stabilization chain is complete and archived:

- `narrative-sovereignty-state-packet-foundation`
- `travel-reconcile-first-autocommit`
- `npc-scene-presence-reconcile-first`
- `validator-authority-deconfliction`

## Sequencing Decision

This continuation SHOULD execute after the gametest version is live and before the OpenRouter router re-architecture.

Execution order:

1. ship and observe the stable OpenAI-based gametest runtime,
2. implement the deferred narrative-sovereignty continuation on that stable baseline,
3. then begin `plans/version-2/openrouter_llm_router_architecture.md`.

Why this order:

- runtime authority boundaries should stabilize before provider-routing changes introduce new variance,
- event-ledger and prompt-reset work are easier to validate on the known provider/runtime baseline,
- it prevents architecture debugging and provider migration from being coupled into the same execution wave.

## Scope

This continuation owns the remaining post-gametest items from the original plan:

1. event ledger foundation for committed world/narrative facts,
2. broader reconcile-first prompt contract reset,
3. optional follow-on cleanup to world-delta reconciliation only if live gametest evidence still shows need.

This continuation does NOT own:

- OpenRouter facade/callsite migration,
- Titans/EGO runtime control loops,
- full planner/narrator split,
- broad combat subsystem redesign.

## Inputs

- `plans/archive/llm-wants-to-be-free.md`
- `plans/version-2/v2-narrative-track.md`
- `plans/version-2/openrouter_llm_router_architecture.md`
- archived OpenSpec changes under `openspec/changes/archive/2026-03-16-*`

## Workstreams

### Workstream 1: Event Ledger Foundation

Primary goal:

- introduce committed event persistence for world and narrative facts that survive beyond immediate turn reconciliation.

Expected outputs:

- new event-ledger helper/module,
- runtime write points for committed soft world events,
- read surfaces for future Titans/EGO and memory systems.

OpenSpec candidate:

- `turn-event-ledger-titans-ready`

### Workstream 2: Prompt Contract Reconcile-First Reset

Primary goal:

- align system and validation prompts with the reconcile-first runtime philosophy already established by G1-G4.

Expected outputs:

- removal of stale reject-first soft-state wording,
- clearer separation between hard mechanical action requirements and soft world-state reconciliation,
- simpler prompt contract that matches runtime truth.

OpenSpec candidate:

- `prompt-contract-reconcile-first-reset`

### Workstream 3: Post-Gametest Transcript Reassessment

Primary goal:

- use live tester transcripts to decide whether additional world-delta reconciliation is needed before Titans/EGO work.

Expected outputs:

- a go/no-go call for any broader world-delta reconciler,
- avoidance of unnecessary architecture expansion if G1-G4 already solved the main UX failures.

## Recommended Order Inside Version-2

1. Event ledger foundation
2. Prompt contract reconcile-first reset
3. Transcript reassessment
4. Only then re-open sequencing for OpenRouter router work

## Relationship to OpenRouter Plan

`plans/version-2/openrouter_llm_router_architecture.md` remains valid, but it should now be treated as downstream of this continuation.

The router re-architecture should consume a more stable runtime authority model, not overlap with the tail end of that stabilization work.

## Exit Criteria

This continuation is ready to hand off to OpenRouter execution when:

1. committed event persistence exists for the targeted soft world-state domains,
2. prompt contracts match reconcile-first runtime behavior,
3. live gametest transcripts show no major unresolved authority-loop class that still needs runtime surgery,
4. the OpenAI baseline remains stable enough to serve as a comparison point for later router migration.

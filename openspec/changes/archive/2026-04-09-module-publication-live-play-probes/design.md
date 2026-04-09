## Context

The publication workflow now has:

- spatial grounding substrate
- semantic-authority substrate
- semantic publication blocker audit

What it still lacks is proof that authored module semantics behave correctly under player-like interactions before release. A semantic authority payload can look structurally correct and still hide live-play problems such as:

- natural-language travel phrases resolving to the wrong destination
- escort or companion handoff semantics drifting between scenes
- hidden or revealable NPCs lacking a stable discovery path under authored clues

The next slice should create deterministic publication probes that execute against authored module semantics and explicit expectations, without relying on runtime LLM behavior.

## Goals / Non-Goals

**Goals:**
- Add deterministic semantic probe execution for publication-time validation.
- Cover the three priority interaction classes in the publication plan:
  - travel
  - escort/handoff
  - hidden/revealable NPC discovery
- Keep probes source-driven using authored fixtures and canonical expected targets.
- Produce structured output stable enough for later CI/readiness/release integration.

**Non-Goals:**
- Implementing the final `publishable` gate.
- Calling live LLMs or replaying runtime narration loops.
- Reworking runtime validators or arrival guards.
- Broadening into unrelated gameplay audits.

## Decisions

### Decision: Probes MUST be deterministic and source-driven
- Rationale: publication validation cannot depend on unstable runtime or provider behavior.
- Approach: define probe fixtures from authored module semantics and compare them against semantic-authority + audit expectations.
- Alternative considered: run the real game loop or live prompt calls for publication testing.
- Rejected because that would be non-deterministic and too costly for publication gating.

### Decision: Probe fixtures SHOULD be explicit and canonical
- Rationale: operators need to know what interaction is being tested and what destination/NPC state is expected.
- Approach: each probe fixture should declare a probe type, source evidence, player-like phrase or clue, expected canonical target, and expected failure class if unresolved.
- Alternative considered: infer all probes dynamically from module metadata at runtime.
- Rejected because initial rollout needs transparent, reviewable fixtures.

### Decision: The harness MUST stop short of repo-wide publishable gating in this phase
- Rationale: this slice is the proof layer, not the final release-policy layer.
- Approach: emit standalone structured pass/degraded/fail probe output and preserve later integration flexibility.
- Alternative considered: wire probes directly into `audit_module_readiness.py` now.
- Rejected because it would combine probe semantics and final gate policy in one change.

### Decision: Failure classes SHOULD align with existing semantic audit policy where possible
- Rationale: the final publishable gate should consume a coherent taxonomy.
- Approach: probe outcomes should reuse or complement Phase 2 blocker concepts such as unresolved destination phrase, ambiguous destination phrase, and missing NPC authority.
- Alternative considered: invent a totally separate probe-only failure vocabulary.
- Rejected because it would create translation work later.

## Proposed Probe Surface

This phase should introduce a standalone script, for example:

- `scripts/module_semantic_probe_harness.py`

Representative output shape:

```json
{
  "module": "Night_of_the_Restless_Dead",
  "status": "fail",
  "summary": {
    "probe_count": 6,
    "pass_count": 3,
    "fail_count": 2,
    "degraded_count": 1
  },
  "probes": [
    {
      "id": "travel.lintars-place",
      "type": "travel",
      "status": "pass",
      "expected_location_id": "NIG08",
      "resolved_location_id": "NIG08"
    }
  ],
  "blocking_errors": [],
  "warnings": []
}
```

## Risks / Trade-offs

- [Fixture authoring becomes too manual] -> Mitigation: start with deterministic fixture derivation from current semantic-authority payload plus bounded explicit fixture overrides only where needed.
- [Probe coverage overlaps semantic audit too heavily] -> Mitigation: keep probes focused on interaction proof, not just static contradiction classification.
- [Probe output becomes too unstable for later gating] -> Mitigation: settle a simple structured output now with fixed pass/degraded/fail semantics.

## Migration Plan

1. Define probe fixture contract and blocking boundaries.
2. Add standalone probe harness and fixture derivation/loading flow.
3. Cover travel, escort/handoff, and hidden-NPC discovery cases with targeted tests.
4. Run the harness on at least one real module with known semantic gaps.
5. Stop before wiring the final `publishable` gate.

## Open Questions

- Should fixtures live entirely in derived audit-time output, or should authored modules support additive explicit probe-fixture hints later?
- Should escort/handoff probes validate only location resolution and NPC continuity, or also party-state expectations in this phase?
- Which current modules provide the best real smoke cases for hidden/revealable NPC discovery without requiring new authored metadata first?

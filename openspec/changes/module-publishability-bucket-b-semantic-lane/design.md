## Context

After the Bucket A quick wins, the next publishability lane is semantic-authority remediation for modules whose media coverage is already mostly or fully complete:

1. `Keep_of_Doom`
   - missing semantic-authority payload
   - unresolved aliases including `breach the keep`, `hidden keep`, and `lantern inn`

2. `Night_of_the_Restless_Dead`
   - missing semantic-authority payload
   - unresolved aliases including `cathedral main hall`, `end ritual chamber`, `main hall`, `ritual chamber`, and `ruined cathedral`

3. `The_Hidden_City_of_Numillian`
   - unresolved `paradox sanctuary`
   - known provenance/sidecar gap
   - semantic ambiguity canary for the next lane

This bucket is intentionally narrower than a general module cleanup pass and intentionally excludes the WIP modules with broad media debt.

## Goals / Non-Goals

**Goals:**
- MUST define a bounded semantic-authority closure lane for `Keep_of_Doom`, `Night_of_the_Restless_Dead`, and `The_Hidden_City_of_Numillian`.
- MUST preserve explicit destination-alias diagnostics and reviewability.
- MUST include Numillian provenance closure because readiness failure there is not purely semantic.
- SHOULD sequence `Keep_of_Doom` and `Night_of_the_Restless_Dead` before Numillian if the goal is simpler semantic-authority payload closure first.

**Non-Goals:**
- NOT broadening into `Murder_at_the_Drowning_Lass` or `The_Ancients_Lab`.
- NOT broadening into a generic all-module semantic rewrite.
- NOT using silent alias suppression to achieve a pass.
- NOT redesigning probe semantics beyond what these named blockers require.

## Decisions

### Decision: Bucket B is a semantic lane, not a media lane
- Rationale: these selected modules already show `100%` monster media base coverage and are blocked elsewhere.
- MUST keep the lane centered on semantic-authority payloads, alias closures, and provenance where required.

### Decision: Keep and Night require explicit semantic-authority payload plus alias closure
- Rationale: both currently fail on missing semantic-authority payload and named unresolved destination phrases.
- MUST plan explicit closure for their named unresolved travel phrases.
- MUST preserve deterministic phrase-to-location authority rather than relying on narrative ambiguity.

### Decision: Numillian remains the semantic ambiguity canary
- Rationale: `paradox sanctuary` is the strongest known Phase 2 ambiguity example and Numillian also has unresolved provenance debt.
- MUST keep `paradox sanctuary` explicit in the plan.
- MUST include sidecar/provenance closure in the same lane because semantic closure alone will not produce a pass.

### Decision: Semantic lane work remains reviewable and fail-closed on ambiguity
- Rationale: publishability should not be won by hiding unresolved destinations.
- MUST preserve explicit blocker surfacing if an alias cannot be uniquely resolved.
- SHOULD treat newly surfaced ambiguity as an expected follow-up, not as silent pass criteria.

## Architecture

### Before

1. These modules have usable media coverage but remain blocked by semantic-authority payload or destination-alias debt.
2. Numillian also fails readiness because provenance/sidecar closure is missing.
3. Publishability remains blocked even though the modules are beyond the heavy media-generation stage.

### After

1. Keep and Night have module-context semantic-authority closure plus deterministic alias coverage for their named blockers.
2. Numillian has both provenance closure and deterministic handling for `paradox sanctuary`.
3. Bucket B can be validated as a semantic/provenance lane independent from the WIP media-heavy modules.

## Risks / Trade-offs

- [Alias closure reveals broader phrase drift] -> Mitigation: keep exact named blocker list in scope and surface additional debt explicitly if found.
- [Numillian still fails after alias closure because provenance remains open] -> Mitigation: keep sidecar/provenance closure in the lane by design.
- [Lane turns into hidden heuristic suppression] -> Mitigation: preserve explicit fail-closed ambiguity handling and reviewable outputs.

## Verification Plan

1. Re-run semantic audit and publishability for `Keep_of_Doom` after semantic-authority and alias closure.
2. Re-run semantic audit and publishability for `Night_of_the_Restless_Dead` after semantic-authority and alias closure.
3. Re-run readiness and publishability for `The_Hidden_City_of_Numillian` after sidecar/provenance plus `paradox sanctuary` closure.
4. Confirm all remaining failures, if any, remain explicitly classified.

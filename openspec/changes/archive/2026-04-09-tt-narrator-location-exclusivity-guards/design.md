## Context

Runtime state already carries authoritative location truth (`currentLocationId`, area connectivity, module topology). The observed failure is not missing state data; it is that narrator output can still present incompatible scene facts. In Thornwood, while state remained in `NC01`, narration instantiated `NC05`-exclusive confrontation elements and fabricated route blockers despite authored adjacency.

The solution should remain narrow and deterministic: keep rich narration, but classify specific contradiction classes as invalid and require correction.

## Goals / Non-Goals

**Goals**
- Enforce current-location truth for present-scene entities/events.
- Preserve atmospheric foreshadowing language.
- Prevent unsupported route-blocking narration when authored adjacency is still available.
- Integrate into existing fail-closed narrator validation/correction flow.

**Non-Goals**
- Rewriting module content.
- Global semantic parser for all fantasy prose.
- Replacing reconcile-first transition logic.

## Decisions

### Decision: Use a two-lane narration contract (foreshadowing allowed, presence constrained)
Narration lane A (foreshadowing) remains permissive for distant threats and implications.
Narration lane B (present-scene claims) is constrained by authoritative location.

Examples:
- Allowed in `NC01`: "you sense Malarok deeper ahead", "a distant ritual pulse".
- Blocked in `NC01`: "Malarok stands before you at the altar", "the Voidstone shard is here".

### Decision: Add a narrow location-exclusivity registry (Thornwood-first)
Implement a small deterministic registry for contradiction-class exclusives:
- `NC05` exclusive present-scene anchors: Malarok present, ritual altar, central Voidstone confrontation.

This keeps implementation safe and testable while enabling future module expansion.

### Decision: Enforce authored-exit grounding separately from exclusivity
When narration claims a connected route is blocked, require deterministic support:
- explicit state/action marking blockage, OR
- module-authored blocker metadata for the route.

If neither exists, reject as unsupported route-blocking drift.

### Decision: Fail closed via existing correction loop
Violations should produce concise correction guidance and retry, not silent rewriting. This preserves operator visibility and avoids hidden state mutation.

## Risks / Trade-offs

- Narrow keyword/anchor checks may miss paraphrases -> mitigate with curated synonyms per exclusive anchor.
- Overly broad checks may reject valid flavor -> keep Thornwood-first and contradiction-class only.
- Route-block grounding could conflict with temporary hazards -> permit explicit deterministic block actions/metadata.

## Migration Plan

1. Add a deterministic helper for location-exclusivity evaluation (Thornwood-first registry).
2. Add narrator validation hook in runtime path to reject contradiction-class present-scene leakage.
3. Add authored-exit grounding check for unsupported blockage claims.
4. Update compressed (and mirror) prompt/validator contract text.
5. Add targeted regressions for NC01/NC05 leakage and false blockage claims.

Rollback:
- Feature-gate helper checks and keep existing narrator flow.
- Prompt additions are additive and can be removed safely.

## Open Questions

- Should module-specific exclusivity metadata eventually live in area files (`scene_exclusive`) or remain code-side registry initially?
- Should blocked-route claims accept narrated hazards if accompanied by deterministic inferred actions, or require explicit actions only?

## Problem
The newly archived `tt-narrator-location-exclusivity-guards` change solved a real contradiction-class bug, but its present-scene exclusivity logic is still code-side and Thornwood-specific. That is acceptable as a first containment fix, but it is not a safe long-term widening strategy.

If we expand by adding more module-specific regex and Python registries, we create three risks:
- runtime lore hardcoding grows faster than authored content
- each new module-specific rule becomes harder to maintain and review
- future broadening becomes brittle and overblocking

The route-block grounding half of the fix is already closer to a scalable pattern because it leans on authored connectivity and existing metadata surfaces like `transition_hints`. The present-scene exclusivity half needs the same treatment.

## Objective
Introduce a low-risk, additive authored metadata contract for scene authority so location-exclusive present-scene guards become metadata-first instead of module-registry-first.

This change should:
- add a location-level `sceneAuthority.presentSceneAnchors` contract
- make runtime prefer authored metadata when available
- preserve the current Thornwood hardcoded fallback during migration
- avoid broad module remediation in the same slice

## Non-goals
- Broad backfill of all existing modules in one pass.
- Removal of the current Thornwood fallback in the same change.
- Universal prose semantics or freeform world-modeling.
- Redesign of travel reconciliation or combat routing.
- New player-facing UI or authoring screens.

## Rollout Risk and Fallback
- Risk: metadata could be malformed, too sparse, or too broad.
- Fallback: if no `sceneAuthority` metadata exists, runtime must keep current legacy behavior.
- Migration safety: Thornwood must retain its current behavior even before any broader module adoption.
- Validator behavior must remain contradiction-class focused; missing metadata in legacy modules must not become a global blocker.

## Compatibility
- The metadata contract must be additive and optional.
- Existing modules without `sceneAuthority` metadata must remain runtime-compatible.
- Existing `transition_hints` and blocker-like metadata surfaces must continue to work unchanged.
- This change should generalize the mechanism, not force immediate project-wide content churn.

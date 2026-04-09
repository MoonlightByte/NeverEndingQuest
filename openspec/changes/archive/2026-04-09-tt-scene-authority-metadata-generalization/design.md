## Architecture Boundaries
- **Schema surface:** additive location metadata only; no required-field breakage for legacy modules.
- **Runtime surface:** `utils/narrator_location_exclusivity_guard.py` becomes metadata-first for present-scene anchor checks.
- **Authoring surface:** area location JSON becomes the source of truth for scene-exclusive anchors.
- **Migration surface:** current Thornwood hardcoded fallback remains until metadata coverage is intentionally expanded.

## Metadata Contract

This change introduces an additive location-level metadata contract:

```json
"sceneAuthority": {
  "presentSceneAnchors": [
    {
      "anchorId": "malarok_present",
      "aliases": ["Malarok", "Malarok the Corruptor"],
      "category": "boss_presence",
      "foreshadowAllowed": true
    },
    {
      "anchorId": "voidstone_altar",
      "aliases": ["Voidstone altar", "Voidstone shard", "ritual altar"],
      "category": "finale_object",
      "foreshadowAllowed": true
    }
  ]
}
```

Contract notes:
- `sceneAuthority` is optional.
- `presentSceneAnchors` is optional.
- `anchorId` and `aliases` are the only required fields for the first rollout.
- `category` and `foreshadowAllowed` are descriptive/behavioral helpers, not a broad new semantic language.

## Detection Model

The widening should stay low risk by keeping the runtime detector narrow:
- use authored anchor aliases to know which scene facts are exclusive to which location
- use bounded present-scene heuristics to distinguish:
  - foreshadowing lane: allowed
  - present-scene lane: constrained by current location truth

Important boundary:
- Do NOT move to author-supplied regex or unrestricted semantic DSL in this change.
- Do NOT attempt universal entity extraction.

## Runtime Behavior

### Present-Scene Exclusivity
- Runtime SHOULD build a module-local anchor index from authored `sceneAuthority.presentSceneAnchors` metadata.
- When metadata exists for a referenced anchor, runtime SHOULD use metadata-first evaluation.
- If metadata does not exist, runtime MUST preserve current fallback behavior.
- During migration, the existing Thornwood-specific guard remains as the fallback path.

### Route-Block Grounding
- This change SHOULD keep route-block grounding on its current low-risk surfaces:
  - authored `connectivity`
  - existing `transition_hints`
  - explicit blocker-like metadata already recognized by runtime
  - deterministic state/actions
- This slice SHOULD NOT introduce a large new blocker ontology unless the existing surfaces prove insufficient.

## Migration Plan
1. Add additive `sceneAuthority.presentSceneAnchors` schema support.
2. Refactor the exclusivity helper to prefer authored metadata.
3. Keep the current Thornwood hardcoded fallback in place.
4. Backfill only Thornwood as the reference implementation for the metadata contract.
5. Add warn-only or report-only tooling/tests for future module adoption.

## Trade-offs
- Keeping the Thornwood fallback increases short-term duplication, but it is the safest migration path.
- Metadata-first widening delays broad coverage, but avoids brittle code-side lore registries.
- Narrow authored metadata is less expressive than a semantic rules engine, but much easier to validate and maintain.

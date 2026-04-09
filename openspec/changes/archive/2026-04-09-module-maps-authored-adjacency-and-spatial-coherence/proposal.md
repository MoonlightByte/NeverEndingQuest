## Why

`plans/module-maps.md` is still open because the spatial contract shape now exists, but the ingest path still seeds topology from source order and the validator still stops at field-shape/parity checks. That leaves a real gap between "spatial fields present" and "spatial layout is semantically grounded enough to trust for future map work and gameplay testing."

This change closes the remaining module-maps slice before publication work begins. The goal is to make new ingest outputs derive adjacency from authored room semantics and to make strict spatial validation fail when new module geometry is clearly incoherent.

## What Changes

- Add deterministic authored-adjacency extraction for Homebrew ingest so room graphs are no longer scaffolded from previous/next ordering alone when stronger authored signals exist.
- Feed extracted ingest adjacency into the shared spatial planner so emitted coordinates and directions are grounded in authored room relationships.
- Upgrade strict spatial validation to detect geometric incoherence, including implausibly distant connected rooms and direction/coordinate contradictions.
- Preserve warn-first behavior for legacy modules and fail-open runtime compatibility for already-shipped content.
- Add targeted importer and validator regressions for non-linear source layouts and strict-vs-legacy behavior.

## Non-Goals

- No `publishable` gate or publication-audit layer.
- No destination phrase map, NPC scene-authority map, or synthetic gameplay probe suite.
- No v2 map UI/runtime payload implementation.
- No runtime movement-validator redesign beyond consuming stronger authored module truth later.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `tt-spatial-coordinate-resolution`: strengthen ingest adjacency grounding and strict spatial coherence validation for new outputs.

## Impact

- Affected ingest path: `core/importers/homebrewery_importer.py`
- Affected shared spatial logic: `utils/spatial_contract.py`
- Affected validator path: `core/validation/validate_module_files.py`
- Affected regressions: `scripts/test_spatial_coordinate_grounding.py` and importer-focused tests
- Merge safety: MUST remain additive and keep builder/remediation/runtime behavior stable outside the narrowed ingest + validation slice
- Compatibility: MUST preserve single-player and tabletop runtime behavior; legacy modules SHOULD remain warn-first until remediated

## Rollout Risk And Fallback

- Risk: authored-adjacency extraction may overfit weak prose and create false graph edges
- Mitigation: extraction MUST remain deterministic, bounded, and fall back to current safe connectivity when authored signals are insufficient
- Risk: stricter validator rules may suddenly fail newly generated modules during active testing
- Mitigation: strict failures MUST apply only to spatial-contract-marked outputs; legacy modules remain warnings-only
- Fallback: if semantic extraction degrades, ingest SHOULD still emit a safe module using current fallback planning rather than hard-crashing mid-pipeline

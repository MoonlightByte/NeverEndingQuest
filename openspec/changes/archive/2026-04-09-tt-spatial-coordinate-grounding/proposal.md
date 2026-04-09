## Problem
Current module creation surfaces do not yet emit a complete spatial authoring contract. Homebrew ingest still falls back to naive linear map placement, and toolkit-generated module data is not yet aligned to emit the same pre-v2 spatial fields consistently. Legacy modules also lack a safe backfill path for richer spatial data.

For upcoming gameplay testing, new modules should already carry the spatial foundations that later v2 mapping work will consume:
- semantically grounded `coordinates`
- per-location `tactical_grid`
- per-location `aliases`
- explicit cardinal `directions` in `map_<AREA>.json`

## Objective
Expand the current spatial-coordinate grounding change into a broader pre-v2 module spatial preparation change.

The change should make new ingest and toolkit builder outputs emit the same spatial data contract now, while keeping runtime mapping UI and worldview work explicitly deferred.

## Non-goals
- v2 map UI, renderers, tabs, or player-facing map flows.
- `memory.db` worldview graph work.
- Combat overlay or threat-radar implementation.
- Runtime dynamic coordinate generation.
- Runtime movement-validator redesign beyond consuming the authored data already produced.

## Rollout Risk and Fallback
- Risk: Spatial enrichment output may be malformed, incomplete, or semantically inconsistent.
- Fallback for legacy content: validator remains warn-first until remediation is run.
- Fallback for runtime: gameplay must remain functional if a legacy module lacks the new fields.
- New build and ingest paths should not silently ship degraded spatial contracts as if they were valid final output.

## Merge-Safety and Compatibility
- MUST preserve authored `connectivity` arrays in legacy modules during remediation.
- MUST keep single-player and tabletop gameplay functional while this remains a data-prep-only change.
- MUST update actual current builder surfaces, not stale targets.

## Why

The uploader can now route markdown uploads through normalization, review, and packet-driven raw module build, but the current contract still treats a successful builder run as the end of the slice even when the emitted module is structurally unready. Real output from `The_Ancients_Lab` proved that `build_completed` can still include unresolved monster references, spatial-contract failures, invalid `party_tracker.json` fields, and generator defects that should never enter the finisher/publication path.

The next change must add a structural readiness gate between raw packet build and finisher/publication so the uploader can distinguish raw artifact creation from a working module. That gate must use Python-first remediation for deterministic failures, bounded semantic repair only where Python cannot infer the fix safely, and fail-closed classification for builder/runtime defects.

## What Changes

- Add a dedicated structural readiness stage after packet-driven build and before finisher/publication.
- Introduce explicit uploader states for `validating`, `repairing_deterministic`, `repairing_semantic`, and `ready_for_finishing`.
- Run canonical module validation and readiness audit on packet-built modules before any finisher step.
- Add deterministic repair passes for repairable structural defects such as enum normalization, monster materialization, spatial contract repair, and derived context/summary regeneration.
- Add bounded semantic repair hooks for targeted missing-placement or plot-hook inconsistencies that Python cannot infer safely.
- Classify generator/runtime exceptions as `build_system_failed` and stop repair loops immediately instead of masking them as content defects.
- Expose grouped validation/repair progress and final readiness outcome in the toolkit UI and persisted job artifacts.
- Keep finisher/publication attachment out of this change; this slice ends when a module reaches `ready_for_finishing` or a bounded failure state.

## Capabilities

### New Capabilities
- `toolkit-homebrew-structural-readiness-gate`: packet-built upload modules pass through an authoritative validation/remediation gate before they are eligible for finishing.

### Modified Capabilities
- `toolkit-homebrew-build-from-packet`: successful builder completion is explicitly pre-readiness and MUST NOT be treated as final module completion.
- `toolkit-homebrew-ingest-job-reporting`: job reporting now distinguishes raw build completion from validation, repair, readiness, and system-failure states.

## Impact

- Affected route/job orchestration surface: `web/routes/toolkit_homebrew_routes.py`
- Likely affected builder integration surface: `web/extensions/toolkit_homebrew_packet_builder.py`
- Likely affected validation/remediation surface: new shared readiness-gate helper under `web/extensions/`, `scripts/`, or `utils/`
- Likely affected toolkit UI surface: `web/templates/module_toolkit.html`
- Authoritative validation surfaces reused: `core/validation/validate_module_files.py`, `scripts/audit_module_readiness.py`
- Possible deterministic repair integrations: monster materialization, context regeneration, spatial contract helpers, party/world normalization helpers
- Merge safety impact: SHOULD remain additive by inserting a post-build gate rather than rewriting the concept-builder or finisher flows
- SP/MP compatibility impact: no gameplay runtime behavior change; MUST remain isolated to toolkit upload workflows
- Rollout risk: more visible states and longer build pipelines may increase latency perception, so progress reporting and grouped fix visibility MUST improve in the same slice

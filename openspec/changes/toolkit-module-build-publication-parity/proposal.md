## Why

The GUI Module Builder currently stops at raw module generation, while the ingest pipeline applies stronger finishing and publication-oriented stages such as continuity normalization, registry verification, and materialization checks. We need to bring the toolkit builder output up to that same post-build quality bar so toolkit-generated modules are closer to ingest-produced modules and future publication standards can attach to one shared finishing path.

## What Changes

- Add a shared post-build finishing pass for toolkit-generated modules after `ModuleBuilder.build_module(...)` succeeds.
- Apply parity stages that MUST include continuity normalization, registry verification, and monster materialization, with optional sidecar/report persistence.
- Add toolkit-visible result reporting for pass, degraded, and fail outcomes from the finishing stages.
- Preserve the existing AI-first Module Builder input model and generation flow.
- Exclude full semantic publication probes, spatial grounding, tactical-grid generation, and PDF import from this change.

## Capabilities

### New Capabilities
- `toolkit-module-postbuild-finishing`: Toolkit-generated modules receive a shared finishing pass that brings them closer to ingest publication readiness.
- `toolkit-module-build-reporting`: The toolkit exposes post-build finishing results with structured pass/degraded/fail reporting instead of a simple success message only.

### Modified Capabilities
- None.

## Impact

- Affected builder execution path: `web/web_interface.py` toolkit build thread/socket flow
- Affected generator/build pipeline: `core/generators/module_builder.py` and a new shared finishing helper/service
- Reused ingest-stage logic: continuity normalization, registry verification, monster materialization, and report/sidecar persistence helpers
- Compatibility: MUST preserve existing concept-builder UX while improving quality gates after generation completes

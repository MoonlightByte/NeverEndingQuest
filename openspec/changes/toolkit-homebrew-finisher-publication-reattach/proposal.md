## Why

The public Homebrew upload path now supports normalization, review, packet-driven build, structural readiness repair, and explicit clean rebuilds for repeated uploads. Upload jobs can stop at `ready_for_finishing`, but they do not yet continue through the hardened finisher/publication pipeline already used by the developer ingest workflow.

This leaves the uploader short of the planned end-state: reviewed uploads can become structurally ready modules, but they cannot yet reach the same continuity, semantic, media, and publishability checks that determine whether a module is actually safe to register.

## What Changes

- Attach the existing toolkit finisher/publication pipeline to upload jobs that have already reached `ready_for_finishing`.
- Require `ready_status=pass` before entering finisher/publication work.
- Require `publishable_status=pass` before registry/world integration is allowed.
- Preserve existing fail-closed behavior for structural, registry, and publishability blockers.
- Preserve existing fail-open degraded behavior for non-core media steps where that behavior already exists in the shared finisher path.
- Expose upload job stages for `finishing`, `publishability_audit`, `completed`, `finishing_failed`, and `not_publishable` distinctly from raw build/readiness states.
- Persist finisher/publication artifacts and summary payloads alongside the existing upload job workspace artifacts.
- MUST reuse the shared finisher/reporting stack rather than inventing an upload-only publication path.
- MUST keep concept-builder flow unchanged.
- SHOULD preserve artifact parity between developer ingest and public upload for the same module.
- Non-goals: redesign normalization, builder prompts, repair budgets, or registry semantics in this slice.

## Capabilities

### New Capabilities
- `toolkit-homebrew-finisher-publication-reattach`: upload jobs that have reached `ready_for_finishing` can enter the shared finisher/publication stack and complete only when publishability passes.

### Modified Capabilities
- `toolkit-homebrew-build-from-packet`: packet-built upload jobs now continue from `ready_for_finishing` into finisher/publication rather than stopping at readiness.
- `toolkit-homebrew-ingest-job-reporting`: job reporting now distinguishes finisher/publication stages and terminal publishability outcomes from readiness-only success.

## Impact

- Affected upload orchestration: `web/routes/toolkit_homebrew_routes.py`
- Affected shared finisher integration: `web/extensions/toolkit_module_finisher.py`
- Affected developer/upload parity points: `scripts/homebrew_ingest_dev.py` shared finishing hooks if extraction is needed
- Affected GUI surface: `web/templates/module_toolkit.html`
- Artifact/reporting impact: finishing reports, publishability outcomes, and terminal job summaries must be persisted in upload workspaces
- Merge-safety impact: SHOULD remain additive by extending the Homebrew upload orchestration only
- SP/MP compatibility impact: no gameplay runtime change; MUST remain toolkit-only
- Rollout risk: medium, because upload orchestration must compose the shared finisher without creating a divergent publication path

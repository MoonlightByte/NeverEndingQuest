## Why

The current uploader sequence is not yet correct for production because review can happen on a placeholder packet instead of a true normalized interpretation of the uploaded markdown. The next change must add the actual LLM-backed normalization engine and restore the intended phase ordering from `plans/module-uploader.md`: routing -> normalizing -> awaiting_review -> approved_for_build.

## What Changes

- Add a dedicated Homebrew normalization engine that reads uploaded markdown and produces a real normalized packet plus normalization report.
- Add a bounded source-faithful normalization prompt that separates grounded facts from inferred assumptions.
- Extend toolkit upload job orchestration so normalization-required uploads enter a `normalizing` stage and only transition to `awaiting_review` after successful packet generation.
- Replace placeholder-only review handoff semantics with true normalized packet handoff semantics.
- Persist `normalized_packet.json`, `normalization_report.json`, and `builder_narrative.txt` as outputs of the normalization phase.
- MUST fail closed on provider, parse, or persistence failures by leaving the job outside review-approved states.
- SHOULD preserve the current concept-builder flow and keep deterministic-ready ingest behavior intact.
- MUST NOT implement build-from-packet or publication integration in this change.

## Capabilities

### New Capabilities
- `toolkit-homebrew-normalization-engine`: LLM-backed normalization service for source-faithful Homebrew markdown interpretation into persisted packet artifacts.

### Modified Capabilities
- `toolkit-homebrew-md-upload`: upload jobs now route through an explicit normalization stage before entering review when normalization is required.
- `toolkit-homebrew-ingest-job-reporting`: toolkit job reporting now exposes `normalizing` and post-normalization handoff state transitions distinctly from routing and final build outcomes.

## Impact

- Affected normalization implementation surface: new helper/service module and prompt files for Homebrew packet generation
- Affected toolkit route/job surface: `web/routes/toolkit_homebrew_routes.py`
- Affected uploader contract helpers: `utils/toolkit_homebrew_upload_contract.py`
- Affected toolkit UI reporting surface: `web/templates/module_toolkit.html`
- Likely affected tests: `scripts/test_toolkit_homebrew_md_upload_routes.py` and new normalization-engine-focused regression coverage
- Merge safety impact: SHOULD remain additive by introducing a dedicated normalizer module and minimal route/job-state hooks
- SP/MP compatibility impact: no gameplay runtime behavior change; MUST stay isolated to toolkit upload workflows
- Provider recovery path: normalization failures MUST keep artifacts inspectable and MUST surface actionable job errors without silently advancing to review

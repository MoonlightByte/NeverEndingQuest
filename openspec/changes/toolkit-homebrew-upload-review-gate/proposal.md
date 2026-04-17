## Why

The toolkit Homebrew upload path can now preserve readable markdown, route it into a stable artifact workspace, and emit a normalized packet placeholder, but it still has no human review boundary before later build and registry-facing stages. The uploader roadmap in `plans/module-uploader.md` explicitly requires mandatory human review, so the next change must turn the preserved packet into an operator-visible review gate instead of leaving jobs stranded at an internal routing state.

## What Changes

- Add a toolkit review surface that reads normalized packet data from the upload workspace and presents a curated review summary for Homebrew upload jobs.
- Add explicit review actions for `approve` and `reject` so upload jobs can move through an authoritative review gate before any build or publication path is allowed to continue.
- Persist a review snapshot artifact that records the operator decision, packet identity, and review timestamp in the upload workspace.
- Extend toolkit upload job state handling so jobs can represent `awaiting_review`, `approved_for_build`, and `rejected` without hiding authoritative routing information.
- Add route handlers and contract enforcement so unreviewed jobs MUST NOT proceed to later build-start or registry-facing stages.
- SHOULD keep first-release review scope limited to review/approve/reject only, without deep inline packet editing.
- MUST preserve the existing concept-builder flow and MUST remain separate from the source-anonymous world-narrative ingestion lane.

## Capabilities

### New Capabilities
- `toolkit-homebrew-review-gate`: mandatory human review workflow for normalized Homebrew upload jobs before build continuation.
- `toolkit-homebrew-review-snapshot`: persisted approval/rejection artifact contract for upload job review decisions.

### Modified Capabilities
- `toolkit-homebrew-md-upload`: upload jobs now stop at an explicit review boundary after normalization-ready packet preparation instead of treating upload completion as equivalent to build readiness.
- `toolkit-homebrew-ingest-job-reporting`: job reporting now exposes authoritative review states and decisions in addition to upload routing and ingest outcomes.

## Impact

- Affected toolkit UI surface: `web/templates/module_toolkit.html`
- Affected toolkit route/job surface: `web/routes/toolkit_homebrew_routes.py`
- Likely affected uploader contract helpers: `utils/toolkit_homebrew_upload_contract.py`
- Likely affected tests: `scripts/test_toolkit_homebrew_md_upload_routes.py` and new/extended review-gate coverage
- Merge safety impact: SHOULD remain additive through new route handlers, workspace artifact persistence, and small toolkit UI extensions rather than broad toolkit rewrites
- SP/MP compatibility impact: no gameplay runtime behavior change; MUST stay isolated to toolkit upload flows
- Rollout risk: users may confuse review completion with build completion, so the UI MUST distinguish review approval from later build execution
- Fallback strategy: if review action persistence fails, the job MUST remain non-approved and artifacts MUST stay inspectable in the workspace rather than silently advancing

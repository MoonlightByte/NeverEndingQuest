## Why

The toolkit Homebrew markdown upload path currently hard-fails when a source is readable but not already shaped like a deterministic NEQ ingest artifact. That blocks the public uploader before LLM interpretation, artifact persistence, or human review can happen, and it prevents the uploader from becoming the final pre-v2 interactive import slice defined in `plans/module-uploader.md`.

We need a first contract-first change that reclassifies preflight as routing instead of parser authority, defines the normalized packet and artifact workspace, and updates the toolkit upload job model so later builder changes can add LLM normalization and review without another schema break.

## What Changes

- Modify Homebrew preflight so it MUST distinguish unreadable source from normalization-required source instead of treating structural ambiguity as a terminal failure class.
- Add a normalized packet contract for toolkit-uploaded Homebrew markdown, including provenance and rights-classification fields required by the uploader roadmap.
- Add a persisted artifact workspace contract for toolkit upload jobs under `user_uploads/toolkit/homebrew_md/`.
- Modify the toolkit markdown upload contract so upload jobs MAY route to deterministic ingest or later normalization/build stages rather than assuming direct strict ingest is always the next step.
- Modify toolkit job reporting so stage/state reporting MUST support upload-era routing states in addition to existing ingest outcomes.
- Exclude implementation of the LLM normalization engine, review UI, and build-from-packet execution from this first change.

## Capabilities

### New Capabilities
- `toolkit-homebrew-normalized-packet`: The toolkit upload pipeline defines a canonical normalized packet contract for readable Homebrew markdown sources that require interpretation before module build or ingest.
- `toolkit-homebrew-upload-artifact-workspace`: Toolkit upload jobs persist source, routing, normalization-contract, and later build artifacts under a stable workspace layout for audit, retry, and rebuild.

### Modified Capabilities
- `homebrew-preflight`: Preflight requirement changes from deterministic readiness gate only to a routing-oriented source classification contract that can return normalization-required outcomes.
- `toolkit-homebrew-md-upload`: Toolkit markdown upload requirement changes so a valid upload starts a staged upload job, not necessarily an immediate strict ingest call.
- `toolkit-homebrew-ingest-job-reporting`: Toolkit job reporting requirement changes so stage reporting can represent upload routing states before strict ingest or build occurs.

## Impact

- Affected planning/contract surface: `plans/module-uploader.md`, `plans/version-2/module-import.md`
- Affected ingest contract code: `scripts/homebrew_preflight.py`, `scripts/homebrew_ingest_dev.py`
- Affected toolkit upload/job surface: `web/routes/toolkit_homebrew_routes.py`, `web/templates/module_toolkit.html`
- New contract artifacts likely needed: normalized packet schema/contract helper and upload artifact workspace helper
- Compatibility: MUST preserve current single-player runtime and concept-builder flow, and MUST keep unreadable uploads fail-closed
- Merge safety: SHOULD prefer additive route/job contract extensions and avoid broad host-file rewrites
- Fallback strategy: if later normalization/build phases are unavailable, readable uploads may stop at a persisted routing/contract stage rather than failing with a misleading structure error

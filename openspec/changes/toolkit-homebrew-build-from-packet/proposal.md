## Why

The uploader now has the first four phases of the interactive import flow in place: routing, normalization, job orchestration, and mandatory review. The current gap is that an approved upload stops at `approved_for_build` with no packet-driven way to enter the rich module builder. The only working builder entrypoint today is the raw concept-builder socket flow, which expects freeform narrative input and immediately continues into post-build finishing.

The next change must connect `normalized_packet.json` plus the review snapshot to a dedicated upload-aware build path so approved uploads can become build artifacts without rerunning normalization or bypassing the review boundary.

## What Changes

- Add a dedicated build-from-packet facade for approved Homebrew upload workspaces.
- Convert `normalized_packet.json` into persisted `builder_input.json` plus builder invocation parameters.
- Start packet-driven builds only from `approved_for_build`, without coupling approval to automatic build start.
- Reuse the upstream module builder internally while preserving upload job ownership and artifact persistence.
- Persist `build_result.json` with packet identity, build mode, and module slug or failure payloads.
- Expose explicit upload-job build states in the toolkit UI and reporting surface.
- Stop this change at build completion; DO NOT reattach post-build finishing, publication, or registry integration yet.

## Capabilities

### New Capabilities
- `toolkit-homebrew-build-from-packet`: approved upload workspaces can launch a dedicated packet-driven module build that persists builder inputs and build results.

### Modified Capabilities
- `toolkit-homebrew-md-upload`: approved upload jobs gain an explicit build-start path that is separate from review approval.
- `toolkit-homebrew-ingest-job-reporting`: upload job reporting distinguishes `approved_for_build`, `building`, and `build_completed` from earlier normalization/review states and later finishing states.

## Impact

- Affected upload route/job surface: `web/routes/toolkit_homebrew_routes.py`
- Affected toolkit UI surface: `web/templates/module_toolkit.html`
- Affected builder integration surface: `web/web_interface.py` and/or a new shared build facade under `web/extensions/`
- Affected artifact contracts: `builder_input.json` and `build_result.json`
- Likely affected tests: `scripts/test_toolkit_homebrew_md_upload_routes.py` plus new packet-to-builder regression coverage
- Merge safety impact: SHOULD remain additive by introducing a dedicated upload-aware builder facade rather than rewriting the concept-builder flow
- SP/MP compatibility impact: no gameplay runtime behavior change; MUST remain isolated to toolkit upload workflows
- Publication boundary: MUST leave finisher, semantic publication probes, and registry integration for the following uploader slice

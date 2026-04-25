# Overview

This change collapses the Homebrew markdown upload flow into a single import-to-build path. Upload still performs the shared ingest and normalization stages, but a successful normalized packet no longer waits in `awaiting_review`. Instead, the job transitions directly into the existing packet build start path. The only remaining interactive pause is the existing overwrite/backup confirmation when the normalized packet resolves to an already-existing module slug.

# Goals

- Make upload behave like a direct build intent.
- Keep destructive rebuild confirmation as the only mandatory user approval step.
- Preserve structured job reporting and packet-based retry semantics.
- Minimize churn by reusing the existing build route and artifact plumbing where practical.

# Non-Goals

- Removing audit/report artifacts produced during normalization.
- Replacing the packet-based retry/rebuild model.
- Changing concept-builder workflows or unrelated toolkit routes.

# Current State

Today the flow is split across three server-side states:

1. Upload runs ingest + normalization and stops at `awaiting_review`.
2. Review approval moves the job to `approved_for_build`.
3. Build start begins only from `approved_for_build` or later collision-confirmation states.

The frontend mirrors that split with a dedicated review panel and three buttons. That is why removing only the buttons would break the happy path.

# Proposed Flow

## Server State Machine

Successful normalization SHOULD do the following in-order:

1. Persist the normalized packet and any review/audit snapshot artifacts.
2. Mark the job as ready to build without requiring a user review decision.
3. Immediately invoke the existing build-start path.
4. If an existing module collision is detected, transition into the current overwrite confirmation wait state and return the same confirmation metadata already used today.
5. If no collision exists, continue into `building` and later `finishing`/terminal states exactly as the current packet build flow does.

This means `awaiting_review` and manual review POST are removed from the primary import flow. Internal snapshot creation may remain for diagnostics and artifact manifest compatibility.

## Frontend Flow

The toolkit UI SHOULD:

- remove the explicit review panel/buttons from the import flow,
- continue polling/refreshing job status,
- surface collision confirmation when the backend returns `requires_confirmation`, and
- continue showing structured progress, errors, artifacts, and final outputs.

The UI should not introduce a replacement approval screen. Import should read as a direct pipeline action.

# Data and Artifact Compatibility

- `artifact_manifest` MUST remain available in job status responses.
- If downstream reporting currently expects `ui_review_snapshot`, the implementation SHOULD keep writing that artifact or provide an equivalent manifest-compatible replacement in the same reporting surface.
- Retry-from-packet MUST keep working from the normalized packet even though manual review is removed.

# Safety Model

The safety boundary shifts from “review before build” to “confirm before destruction.”

- Non-destructive packet builds may start automatically.
- Destructive rebuilds of an existing module MUST still wait for explicit confirmation.
- Validation, normalization, and readiness failures MUST still fail closed before build.

# Implementation Strategy

## Backend

- Update upload/normalization completion to stop using `awaiting_review` as the normal next state.
- Reuse the build-start logic instead of duplicating build orchestration inside upload.
- Preserve collision detection and `awaiting_overwrite_confirmation` handling.
- Either retire the review-decision route from the import UX path or leave it unused/compatibility-only if that lowers rollout risk.

## Frontend

- Remove the review action controls from `module_toolkit.html`.
- Replace review-panel-driven progression with direct job-status/build-status progression.
- Keep overwrite confirmation modal behavior unchanged.

## Tests

- Update route tests to expect auto-start after normalization.
- Preserve explicit assertions for collision confirmation, backup metadata, retry-from-packet, and terminal reporting.
- Remove or rewrite tests that encode `awaiting_review` as the happy-path stop state.

# Risks and Mitigations

- Risk: hidden dependency on `awaiting_review` in job reporting or UI rendering.
  - Mitigation: update status/reporting tests and preserve artifact manifest compatibility.
- Risk: duplicated build invocation paths if upload launches build in an ad hoc way.
  - Mitigation: funnel auto-start through the existing packet build route/helper logic.
- Risk: accidental removal of destructive confirmation.
  - Mitigation: keep existing-module collision and backup semantics unchanged and explicitly test them.

# Verification

- OpenSpec validation for the new change passes.
- Route tests prove successful upload proceeds directly into build or overwrite-confirmation wait.
- UI contract no longer exposes approve/reject/start-review controls.
- Retry-from-packet and overwrite confirmation behavior remain intact.

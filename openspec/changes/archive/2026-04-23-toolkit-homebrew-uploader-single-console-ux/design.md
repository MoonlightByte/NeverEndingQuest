# Design: toolkit-homebrew-uploader-single-console-ux

## Overview

This change simplifies the default Homebrew uploader presentation while keeping the existing auto-start build flow and destructive rebuild safeguards intact. The builder already auto-starts after normalization; this design changes how that process is shown to users.

The default user experience becomes:
1. Upload markdown.
2. Watch one live rolling console/readout window.
3. Confirm overwrite only if an existing module would be replaced.
4. Receive one clear success or failure end-state message.

Operator-style recovery and artifact actions remain available only through an advanced/dev-oriented surface or equivalent non-default path.

## Goals

- Collapse the uploader into one primary console/readout surface.
- Make active progress legible without requiring internal pipeline knowledge.
- Preserve explicit destructive confirmation for module replacement.
- Preserve artifact/reporting contracts for diagnostics and advanced use.

## Non-Goals

- Reworking the ingest/build state machine.
- Removing artifact-manifest generation or advanced recovery endpoints.
- Changing module rebuild safety semantics.

## UX Model

### Default Surface

- One primary uploader panel contains:
  - a short status heading,
  - one rolling console/output window,
  - a lightweight active-work indicator,
  - a final terminal success or failure message.
- The console is the canonical user-facing status surface during upload/build progression.
- The overwrite confirmation remains modal or otherwise explicit when destructive rebuild is required.

### Console Content

- While running, the console should stream or append meaningful status updates from existing job state.
- If richer summaries are unavailable, the console may fall back to raw stdout-like output.
- Multi-panel status boxes, artifact workspace listings, and operator-oriented labels should not appear in the default surface.

### End States

- Success message should clearly state that the module build completed and direct the user to the MMG tab for media generation.
- Failure message should clearly state that the upload/build failed and direct the user to developer help, including `https://github.com/zeug-zz/NeverEndingQuest-TTRPG/issues`.

## Reporting and Artifact Strategy

- Existing structured `status`, `stage`, and artifact-manifest payloads remain authoritative runtime data.
- The default surface presents a simplified projection of that data rather than exposing the full operator model.
- Artifact-backed recovery actions (`retry-from-packet`, `retry-from-finishing`, `cleanup`) remain supported behind advanced/dev access where practical.

## Safety Model

- Non-destructive upload/build progress requires no extra user approval beyond the upload action itself.
- Destructive module replacement still requires explicit operator confirmation and existing backup-before-cleanup protections.
- This change must not create any new path that bypasses overwrite confirmation.

## Implementation Strategy

### Frontend

- Refactor the current uploader panel in `web/templates/module_toolkit.html` so the default flow renders one primary console panel.
- Remove operator-style action buttons from the default surface.
- Route active polling updates into a single rolling log/readout.
- Keep overwrite confirmation wiring unchanged except for integrating it into the single-console flow.
- Add clear success/failure terminal messaging and active-work affordance.

### Backend / Data Contracts

- No major backend state-machine changes are required.
- Existing job status, stage, artifact manifest, rebuild eligibility, and cleanup flags remain available.
- If needed, add small payload helpers that make console-friendly messages easier to render without changing underlying state contracts.

### Test Strategy

- Update uploader template/source-contract tests to assert removal of default-surface retry/cleanup controls and presence of the single-console UX markers.
- Preserve route/integration tests that verify artifact-manifest compatibility and destructive confirmation behavior.
- Validate that advanced/dev recovery capability remains reachable without being present in the default user surface.

## Risks and Mitigations

- Risk: simplified UI hides too much state.
  - Mitigation: preserve structured backend payloads and append meaningful console messages for key state transitions.
- Risk: recovery paths become inaccessible.
  - Mitigation: move them behind advanced/dev access rather than deleting them.
- Risk: console messaging becomes stale or misleading.
  - Mitigation: derive console output directly from existing job status/stage transitions and terminal results.

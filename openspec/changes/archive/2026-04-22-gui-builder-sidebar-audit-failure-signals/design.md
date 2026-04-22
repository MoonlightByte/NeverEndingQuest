# Design: gui-builder-sidebar-audit-failure-signals

## Context

The right-hand GUI Module Builder sidebar currently renders registry metadata only. For modules like `Murder_at_the_Drowning_Lass` and `The_Ancients_Lab`, the user cannot tell from the card that the last toolkit build failed or whether manual `Module Media Generator` work is still required. Existing persisted toolkit reports already encode this information, but the sidebar does not consume it.

The codebase also has duplicate sidebar renderers:

- `web/templates/module_toolkit.html`
- `web/templates/module_builder.html`

The payload originates from `core/generators/module_stitcher.py` through the existing module-list path.

## Goals / Non-Goals

### Goals

- Surface a brief, red, build-failure message on affected module cards.
- Surface a short secondary message when the module still needs manual media generation.
- Reuse persisted report artifacts so the sidebar remains deterministic and fast.
- Keep the implementation additive and fail-open.

### Non-Goals

- Replace or expand the underlying audit system.
- Surface full nested blocker details in the sidebar.
- Add expensive runtime auditing or background caching infrastructure.

## Decisions

### Decision 1: Persisted report is the authority for sidebar enrichment

**MUST** use persisted report artifacts instead of live audits during sidebar rendering.

Reasoning:
- The user wants a brief pipeline-status hint, not a fresh audit.
- Persisted reports already represent the last known build state.
- Running live audits in the sidebar would add latency and introduce watcher/toolkit source mismatches.

Preferred source order:
1. `modules/<slug>/toolkit_build_report.json`
2. optional lightweight fallback only if needed later

### Decision 2: Payload enrichment stays additive

**MUST** preserve the existing module-list payload shape and append only small optional fields such as:

- `brief_failure`
- `media_generator_needed`
- optionally `ready_status`
- optionally `publishable_status`

This avoids coupling the UI to large nested report structures.

### Decision 3: Message derivation stays heuristic but bounded

**MUST** keep the new user-facing message brief and stable.

Suggested derivation priority:
1. If report indicates media-only or dominant structural media debt -> brief failure like `Build failed: missing monster media`
2. If report indicates mixed missing monster JSON + media debt -> brief failure like `Build failed: missing monsters/media`
3. If semantic/travel blockers dominate -> brief failure like `Build failed: destination issues`
4. Else fallback to generic `Build failed: not ready`

**SHOULD** prefer a minimal set of recognizable categories rather than trying to summarize every blocker.

### Decision 4: Media handoff is secondary UI

**MUST** keep the manual media-generator indicator visually secondary to the main red failure message.

Suggested copy:
- `Needs Module Media Generator`

The signal should appear only when report categories or media-policy fields clearly show manual media debt.

## Architecture

### Backend shaping

Recommended touchpoint:
- `core/generators/module_stitcher.py`

Implementation shape:
- keep `get_available_modules()` / `list_available_modules()` as the authoritative list source
- for each module, opportunistically read `modules/<slug>/toolkit_build_report.json`
- derive compact additive fields
- fail open on missing file, malformed JSON, or unsupported shape

This centralizes shaping once for both frontends.

### Frontend rendering

Both templates render the same module-card metadata.

Each renderer should:
- insert a short red failure line below `Plot Points` when `brief_failure` is present
- insert a secondary line for `media_generator_needed`
- preserve existing card layout and click behavior

## Risks / Trade-offs

- Report freshness is only as good as the last toolkit run.
- Brief message derivation may flatten mixed failures into a single line.
- Duplicated template renderers increase sync risk if only one is updated.

## Migration Plan

1. Add backend helper(s) that read persisted reports and derive compact fields.
2. Attach additive fields to module-list payload entries.
3. Update `module_toolkit.html` renderer.
4. Mirror the same rendering change in `module_builder.html`.
5. Verify failed, passing, missing-report, and malformed-report paths.

## Rollback Plan

- Remove additive payload fields from the module list.
- Remove the two UI lines from the duplicate renderers.
- Existing module cards continue to function with no state migration required.

## Verification Plan

**MUST** verify:
- existing module list still renders when reports are absent
- failed modules render brief failure text in red
- media-required modules render the secondary handoff text
- both duplicate templates stay aligned
- no live audit invocation is introduced into the sidebar flow

**SHOULD** include targeted tests for message derivation and fail-open behavior.

## Open Questions

- Whether a lightweight fallback artifact is worth supporting for modules that lack `toolkit_build_report.json`
- Whether the brief copy should be entirely derived from categories or allow a tiny curated mapping for known common failure combinations

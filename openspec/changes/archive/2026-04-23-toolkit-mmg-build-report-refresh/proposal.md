# toolkit-mmg-build-report-refresh

## Why

The Module Media Generator (MMG) shows live media completeness by scanning module media files, but the Module Builder sidebar reads persisted status from `modules/<slug>/toolkit_build_report.json`.

Today those two surfaces can drift. A module can show complete media inside MMG while Module Builder still shows `Build failed: missing monster media` and `Needs Module Media Generator` because the persisted build report was not refreshed after MMG completed.

This creates a false remediation loop for operators and undermines the builder/sidebar contract that persisted reports are the authoritative status source.

## What Changes

### New Capabilities

- Define MMG completion as an explicit persisted report refresh path.
- Define sidebar refresh behavior after MMG success so duplicate module-card renderers reflect updated persisted status without manual rebuild/reload steps.

### Modified Capabilities

- Toolkit build reporting SHALL treat successful MMG media generation as a publishability-affecting workflow that can rewrite `toolkit_build_report.json` through the shared refresh helper.
- Existing module sidebars in Module Builder and Module Toolkit SHALL continue to consume persisted report fields only, but SHALL receive refreshed module-list data after MMG completion.

## Capability Scope

### MUST

- Successful MMG generation SHALL invoke the shared toolkit build report refresh path for the affected module.
- Report refresh failure SHALL be fail-open for MMG completion: media generation success MUST still be reported even if report refresh degrades.
- Sidebar state SHALL continue to come from persisted report data rather than live MMG recomputation.
- After MMG completion, both module-card renderers SHALL be able to display updated persisted failure/handoff signals without requiring a separate build run.
- The implementation SHALL remain narrow to toolkit/reporting GUI flows and SHALL NOT change gameplay runtime behavior.

### SHOULD

- The MMG completion path should reuse `refresh_toolkit_build_report(...)` rather than introducing a bespoke writer.
- Sidebar refresh should reuse the existing `request_module_list` / `module_list_response` path instead of creating a second module-status API.
- The change should preserve current MMG UX even when report refresh degrades.

## Non-Goals

- Reworking how MMG determines live media completeness in its own table.
- Redesigning module card copy or adding new sidebar badges.
- Adding live audit execution to sidebar rendering.
- Broad uploader or finisher architecture changes outside the MMG completion path.

## Impact

- Affected code:
  - likely `web/web_interface.py`
  - likely `web/templates/module_toolkit.html`
  - targeted report-refresh regression tests
- Affected systems:
  - MMG unified asset generation completion flow
  - persisted toolkit build report refresh path
  - Module Builder / Module Toolkit sidebar module-list refresh behavior
- Merge-safety impact:
  - Low. This is a narrow GUI/reporting synchronization fix.
- SP/MP compatibility impact:
  - Neutral. Toolkit only.
- Rollout / fallback:
  - If report refresh fails, MMG still completes and existing persisted sidebar status remains until the next valid refresh path runs.

## Risks

- Over-refreshing module list state could create duplicate UI refresh events.
- A refresh hook in the wrong MMG branch could rewrite reports before media writes are actually complete.
- Coupling MMG directly to report writing instead of the shared helper could create contract drift.

## Fallback

- Preserve current MMG completion behavior if the shared report refresh helper fails.
- Keep sidebar consumers on the last persisted report rather than switching to live MMG-derived state.

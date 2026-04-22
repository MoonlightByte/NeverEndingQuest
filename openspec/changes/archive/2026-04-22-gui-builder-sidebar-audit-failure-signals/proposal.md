# gui-builder-sidebar-audit-failure-signals

## Why

World-registry modules in the GUI Module Builder right-hand sidebar can currently appear as ordinary entries even when their last toolkit build failed structural or media gates. This hides actionable failure state from the facilitator during manual build workflows and forces them to inspect module directories or run separate audits to understand whether the module still needs manual `Module Media Generator` work.

The sidebar needs a short, high-signal failure indicator that helps the user decide whether the module is ready for further manual build steps without turning the card into a full diagnostics surface.

## What Changes

### New Capabilities

- Add additive sidebar payload enrichment for world-registry module cards using persisted per-module build artifacts.
- Show a brief red audit-failure message on failed modules, ideally below `Plot Points` in the module card.
- Show a short manual handoff indicator when the persisted report says the module still needs `Module Media Generator`.

### Modified Capabilities

- `request_module_list` / `list_available_modules()` SHALL remain the existing sidebar data path, but MAY attach new additive fields derived from persisted toolkit reports.
- Both duplicate sidebar renderers in `web/templates/module_toolkit.html` and `web/templates/module_builder.html` SHALL stay behaviorally aligned for this UX.

## Capability Scope

### MUST

- The sidebar SHALL use persisted report artifacts only and SHALL NOT invoke live audit scripts during module-list rendering.
- Failure copy SHALL be brief, user-facing, and framed as a build-pipeline failure rather than a raw audit dump.
- The UI SHALL fail open when a report is missing or malformed by omitting the new signal rather than breaking the module list.
- The implementation SHALL remain merge-safe and additive, with minimal host-file edits and no change to existing module selection behavior.

### SHOULD

- Failure copy should fit on one short line when possible.
- The media handoff line should be visually secondary to the primary red failure text.
- Report parsing should prefer `modules/<slug>/toolkit_build_report.json` and only use simpler fallback artifacts if needed.

## Non-Goals

- Running publishability, readiness, semantic, or gameplay audits live from the sidebar.
- Rendering full blocker lists or deep remediation detail inside the module card.
- Redesigning the module card layout beyond the new brief failure/handoff text.
- Changing module build semantics, toolkit finisher behavior, or media generation workflow.

## Impact

- Affected code:
  - `core/generators/module_stitcher.py`
  - `web/templates/module_toolkit.html`
  - `web/templates/module_builder.html`
  - possibly `web/web_interface.py` only if light payload shaping is cleaner there
- Affected systems:
  - GUI Module Builder sidebar rendering
  - persisted toolkit build report consumption
- Merge-safety impact:
  - Low. This is an additive payload-and-rendering change with no runtime flow rewrite.
- SP/MP compatibility impact:
  - Neutral. This is toolkit UI only and does not alter gameplay behavior.
- Rollout / fallback:
  - If a module has no usable persisted report, the sidebar continues rendering the existing card with no failure signal.

## Risks

- Persisted reports may be stale or absent for some modules, which can create uneven coverage.
- Overly specific message derivation could become brittle if report shapes drift.

## Fallback

- If a persisted report cannot be parsed reliably, omit the new fields and preserve the existing sidebar card.

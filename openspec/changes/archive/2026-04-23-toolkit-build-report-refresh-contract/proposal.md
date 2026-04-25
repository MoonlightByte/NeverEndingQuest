# toolkit-build-report-refresh-contract

## Why

`modules/<slug>/toolkit_build_report.json` is now the cheap, persisted truth source for GUI Module Builder sidebar status. The sidebar correctly avoids live audits, but that also means stale or partially refreshed reports can mislead the operator after later remediation work changes a module's real blocker state.

This is currently visible in modules like `The_Hidden_City_of_Numillian`, where resolved media or destination issues can remain visible in the sidebar because the persisted report was not refreshed at the right point in the toolkit workflow. Before the broader `plans/module-uploader-2.md` structural stabilization work continues, the repository needs a narrow contract defining when `toolkit_build_report.json` is authoritative, when it is stale, and which toolkit workflows MUST rewrite it.

## What Changes

### New Capabilities

- Define a refresh contract for `toolkit_build_report.json` so persisted sidebar-facing build reports remain aligned with the latest toolkit finishing and remediation state.
- Define explicit freshness metadata for persisted toolkit build reports.
- Define a deterministic refresh path for report-producing toolkit flows without making the sidebar run live audits.

### Modified Capabilities

- Toolkit post-build finishing SHALL continue to produce the final machine-readable report, but SHALL also own the report freshness contract.
- Toolkit remediation and revalidation workflows MAY refresh the persisted report, but only through explicit report-rewrite paths rather than implicit sidebar-time recomputation.

## Capability Scope

### MUST

- `toolkit_build_report.json` SHALL remain the sidebar's persisted read-only source and the sidebar SHALL NOT invoke live audits.
- The change SHALL define when a persisted report is authoritative versus stale.
- The change SHALL define which toolkit flows MUST rewrite the persisted report after publishability-affecting state changes.
- Persisted toolkit reports SHALL carry compact freshness metadata suitable for downstream consumers and debugging.
- The implementation SHALL remain additive and merge-safe, with no gameplay runtime changes.

### SHOULD

- Freshness metadata should identify the producing workflow and latest evaluation stage.
- Refresh semantics should align with existing toolkit finisher/reporting contracts rather than creating a parallel reporting system.
- The contract should support follow-up `module-uploader-2` structural work without requiring another sidebar-specific redesign.

## Non-Goals

- Implementing the full `module-uploader-2` structural stabilization plan.
- Adding LLM-driven remediation or builder integration in this slice.
- Making the sidebar recompute readiness or publishability on demand.
- Redesigning module card copy or adding deeper diagnostics to the sidebar.

## Impact

- Affected code:
  - likely `web/extensions/toolkit_module_finisher.py`
  - report-writing helpers and/or shared toolkit reporting utilities
  - targeted regression tests around persisted report freshness
- Affected systems:
  - toolkit post-build report writing
  - module remediation/revalidation report refresh
  - GUI Module Builder sidebar trust in persisted reports
- Merge-safety impact:
  - Low. This is a reporting-contract hardening change and SHOULD stay within toolkit/reporting paths.
- SP/MP compatibility impact:
  - Neutral. This is builder/reporting only.
- Rollout / fallback:
  - If freshness metadata or refresh hooks are unavailable, existing report writing remains the fallback, but the change should preserve fail-open behavior for readers.

## Risks

- Refreshing too many flows could create duplicate or conflicting report writes.
- Over-specifying freshness could couple the contract too tightly to one finisher implementation.
- Narrowing authority incorrectly could hide legitimate degraded states if the latest rewrite path is incomplete.

## Fallback

- Keep the sidebar read-only and continue consuming the latest persisted report on disk.
- If a refresh-producing workflow cannot complete, preserve the prior report and record explicit freshness/degraded metadata instead of synthesizing live status in the sidebar.

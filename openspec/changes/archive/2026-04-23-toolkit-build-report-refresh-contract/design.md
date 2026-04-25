# Design: toolkit-build-report-refresh-contract

## Context

The GUI Module Builder sidebar now consumes `modules/<slug>/toolkit_build_report.json` as its fast persisted truth source. That is the correct read path, but the repository does not yet have a sharp contract for when that file is current.

Today the same module may move through several publishability-affecting steps after its initial toolkit build:

- toolkit post-build finishing
- semantic or structural remediation
- manual media handoff completion
- targeted revalidation or re-audit

Without an explicit refresh contract, the persisted report can lag behind the module's real state, causing stale sidebar signals and confusing remediation guidance.

## Goals / Non-Goals

### Goals

- Define when `toolkit_build_report.json` is authoritative.
- Define the minimum freshness metadata needed for downstream consumers.
- Define which toolkit workflows are allowed or required to rewrite the persisted report.
- Keep sidebar consumption read-only and deterministic.
- Prepare a clean prerequisite for later `module-uploader-2` structural work.

### Non-Goals

- Replacing readiness or publishability evaluation logic.
- Moving report reads into live audits.
- Solving every uploader/finisher bug in this slice.
- Adding LLM participation in report generation.

## Decisions

### Decision 1: Toolkit finisher remains the primary report authority

**MUST** preserve toolkit post-build finishing as the canonical producer of `toolkit_build_report.json` for a new toolkit build.

Reasoning:
- Existing specs already bind build reporting to post-build finishing.
- Introducing a second primary writer would increase drift risk.
- The sidebar already assumes one compact persisted artifact.

### Decision 2: Refresh paths are explicit, not implicit

**MUST** define explicit report-refresh workflows for later publishability-affecting steps.

Examples of eligible refresh paths:
- finisher completion after a toolkit build
- explicit remediation/revalidation workflow that updates canonical module state
- explicit publishability refresh action that re-evaluates the module and rewrites the persisted report

**MUST NOT** allow sidebar reads to trigger evaluation.

### Decision 3: Freshness metadata is compact and operational

Persisted toolkit reports **MUST** carry freshness metadata sufficient to answer:
- when the report was last written,
- which workflow wrote it,
- which evaluation stage/state it reflects,
- whether the report is current, degraded, or known-stale.

Suggested fields:
- `report_written_at`
- `report_source`
- `report_stage`
- `report_freshness`

The exact field names may vary during implementation, but the contract MUST expose these semantics in machine-readable form.

### Decision 4: Stale is a first-class state

The contract **MUST** distinguish between:
- current authoritative report
- degraded but usable report
- known-stale report

This matters because a stale report may still be the only artifact on disk, and readers need a deterministic interpretation without recomputing live state.

### Decision 5: Sidebar remains a passive consumer

The sidebar **MUST** continue to consume persisted report fields only.

It may later choose to render freshness information, but this slice does not require a sidebar redesign. The main purpose here is to make the persisted artifact trustworthy again.

## Architecture

### Report producers

Primary producer:
- toolkit finisher/reporting path

Secondary explicit refresh producers:
- toolkit remediation or revalidation paths that intentionally recompute publishability-facing report state

All producers should converge on one shared report-writing contract rather than inventing ad hoc JSON shapes.

### Freshness model

The implementation should treat report freshness as metadata attached to the persisted artifact, not as hidden knowledge in the producing workflow.

Recommended model:
- `current`: report reflects the latest known publishability-affecting state
- `degraded`: latest write completed with partial/reportable degradation
- `stale`: module state changed after the last authoritative report write, or a later workflow knows the report no longer reflects current module state

### Read path

No change in principle:
- `core/generators/module_stitcher.py` and similar consumers read the persisted report
- consumers do not run live audits
- fail-open behavior remains in place when the report is absent or malformed

## Risks / Trade-offs

- Too many refresh hooks may make it harder to reason about the final writer.
- Too few refresh hooks will preserve today's stale-report problem.
- A freshness contract without shared write helpers may drift across workflows.

## Migration Plan

1. Define freshness metadata and writer expectations in the report contract.
2. Identify the canonical report-writing helper/path used by toolkit finisher.
3. Extend eligible remediation/revalidation flows to rewrite the persisted report through that same contract.
4. Add regression coverage proving stale known modules get refreshed into current blocker classes.
5. Re-check sidebar behavior against persisted reports only.

## Rollback Plan

- Remove freshness metadata additions from the report contract.
- Revert extra refresh hooks while keeping the existing finisher report write.
- Sidebar remains on the last persisted report with existing fail-open behavior.

## Verification Plan

**MUST** verify:
- toolkit builds still write `toolkit_build_report.json`
- the report includes machine-readable freshness metadata
- an explicit post-build remediation/revalidation flow can rewrite the persisted report
- stale nested historical data no longer remains the only sidebar truth after a valid refresh path runs
- sidebar/report consumers still avoid live audit execution

**SHOULD** verify with canary modules:
- `The_Hidden_City_of_Numillian` reflects current blocker class after refresh
- `Murder_at_the_Drowning_Lass` reflects its current blocker class without generic drift

## Open Questions

- Which existing remediation entrypoint is the narrowest correct place to trigger a report rewrite after manual fixes?
- Whether known-stale state should be written immediately when a module is modified, or only when a later workflow detects/report-refreshes it.

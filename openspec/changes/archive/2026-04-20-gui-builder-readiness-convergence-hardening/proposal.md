## Why

`The_Hidden_City_of_Numillian` no longer fails because of monster hydration or toolkit provenance plumbing; it now fails because the readiness repair loop reaches a fixed point and exhausts its budget without converging through schema validation. We need a bounded deterministic convergence layer so repeated repair passes stop looping, classify the remaining blocker families, and add targeted repair coverage for the blocker classes the current engine still cannot resolve.

This change is needed now because the prior structural and remediation slices have successfully separated source-contract bugs from real readiness debt. The next bottleneck is repair convergence, and Numillian is now the correct canary for that work.

## What Changes

- Add a deterministic readiness convergence workflow that MUST stop on unchanged blocker sets and classify the residual validator families instead of spending more repair budget.
- Add targeted deterministic repair coverage for the known Numillian blocker classes:
  - monster schema completion for hydrated/generated monster JSON,
  - monster reference closure when authored references still lack module monster files,
  - explicit finale prerequisite repair for downstream plot points,
  - spatial adjacency convergence for connected rooms whose coordinates remain non-cardinal after remediation.
- Persist convergence-oriented reporting so canary reruns can distinguish:
  - repaired-to-ready,
  - fixed-point non-convergence,
  - residual content debt after repair coverage is exhausted.
- Re-run Numillian as the primary readiness convergence canary and require the workflow to advance beyond the current `repair_budget_exhausted` fixed point.
- Preserve strict fail-closed readiness semantics for unresolved blockers. This change MUST improve deterministic repair coverage, not weaken validator standards.

Non-goals:

- This change MUST NOT add Phase 2 LLM-assisted classification.
- This change MUST NOT relax gameplay/media blockers for real combatants.
- This change MUST NOT broaden toolkit-source success expectations to legacy non-toolkit modules.
- This change SHOULD avoid reopening already-landed provenance-ordering or semantic degraded-vs-blocking policy work except where convergence reporting needs to reference those results.

## Capabilities

### New Capabilities
- `toolkit-readiness-convergence-hardening`: deterministic repair-pass convergence rules, residual blocker classification, canary-oriented reporting, and repair coverage matrix expectations for toolkit readiness flows.

### Modified Capabilities
- `homebrew-ingest-monster-materialization`: hydrated/generated monster outputs must satisfy schema-complete module monster requirements, not merely file existence.
- `tt-monster-reference-integrity-validation`: unresolved monster references must remain consumable by convergence repair/classification flows and support deterministic closure reporting.
- `module-plot-progression-path-validation`: finale prerequisite failures must support deterministic remediation or explicit residual classification.
- `tt-spatial-coordinate-resolution`: remediation must either converge connected-room adjacency or classify the contradiction as unresolved structural debt without looping.
- `module-publishability-reporting`: reporting must expose readiness convergence outcomes distinctly from final publishability results.

## Impact

- Affected code is expected in readiness/remediation tooling, module validation/remediation helpers, monster materialization/closure helpers, spatial remediation, plot repair paths, and toolkit/readiness reporting surfaces.
- Primary systems affected:
  - toolkit readiness pipeline,
  - module validator/remediation loop,
  - module monster hydration/materialization,
  - plot progression validation/repair,
  - spatial remediation/validation,
  - readiness and publishability reporting artifacts.
- Merge-safety impact MUST stay low:
  - prefer extension/tooling files over host runtime rewrites,
  - mark unavoidable host edits with `# TABLETOP MODE:`.
- SP/MP compatibility impact SHOULD be neutral because this slice targets module-authoring and validation workflows rather than live tabletop combat/runtime behavior.
- Rollout risk:
  - under-repair leaves current fixed-point failures unchanged,
  - over-repair could mutate authored module intent incorrectly.
- Fallback strategy MUST be fail-closed and explicit:
  - if a repairer cannot prove a safe deterministic fix, it must classify the blocker and stop,
  - the system must surface that residual blocker class in reporting rather than retrying indefinitely.

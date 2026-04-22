# Design: GUI Builder Semantic Remediation Reporting

## Context
The deterministic GUI-builder chain is already in place:
- media-only handoff semantics
- workflow ordering
- gameplay/readiness payload normalization
- mixed-failure classification

What remains is a presentation gap. The backend already emits the data needed to guide semantic remediation:
- `remediation_categories`
- `blocking_errors`
- `blocking_findings`
- `ready_status` / `publishable_status`

The current toolkit UI does not convert that into a clear operator workflow. Instead, it often shows raw JSON in failure states.

## Goals
- Surface semantic remediation as a first-class post-build lane for any module with semantic publishability blockers.
- Reuse existing structured audit data instead of inventing a parallel payload shape.
- Keep media handoff, semantic remediation, and mixed-failure outcomes distinct.

## Non-Goals
- Automatic semantic repair.
- LLM-generated remediation proposals.
- Changes to semantic extraction logic or blocker classification rules.
- Replacing Python authority over `publishable_status`.

## Decisions

### Decision: Semantic remediation SHALL be a reporting/rendering slice
This change SHALL focus on toolkit payload interpretation and operator-facing rendering, not on changing the underlying semantic audit rules.

### Decision: Existing structured publishability fields SHALL remain the source of truth
Toolkit rendering SHALL consume the existing structured fields from publishability/readiness output:
- `remediation_categories`
- `blocking_findings`
- `blocking_errors`
- `toolkit_media_policy`

### Decision: Mixed failures SHALL remain failed
If semantic blockers coexist with media debt, the toolkit SHALL preserve failed semantics and show both remediation lanes explicitly.

### Decision: Semantic remediation SHALL remain review-only
The UI/reporting layer SHALL tell the operator what class of authored defect exists and where it came from, but SHALL NOT auto-edit module data.

## Architecture
- Extend toolkit result rendering to detect semantic blocker categories and structured blocker details from `finishing_report` / job result payloads.
- Add a semantic remediation formatter for publishability findings, parallel to the existing hydration-aware formatting.
- Keep the final status contract unchanged: `success_with_media_handoff` remains narrow; semantic and mixed cases remain blocked.

## Risks / Trade-offs
- Over-formatting could hide raw evidence; preserve access to raw payloads for debugging.
- UI-only fixes without test coverage would regress easily; targeted source-contract coverage is required.

## Migration Plan
1. Define the exact UI/report contract for semantic-only and mixed-failure cases.
2. Implement bounded semantic remediation rendering in toolkit surfaces.
3. Add targeted regression coverage.
4. Verify against representative modules with semantic-only and mixed blockers.

## Verification Plan
- `python3 -m py_compile web/web_interface.py`
- Run targeted toolkit/reporting tests covering media-only, semantic-only, and mixed-failure cases.
- Confirm the toolkit UI/report surfaces a semantic remediation section for any module with semantic blockers and does not downgrade mixed failures to media handoff.

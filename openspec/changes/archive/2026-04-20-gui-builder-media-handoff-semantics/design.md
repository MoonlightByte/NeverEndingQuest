# Design: GUI Builder Media Handoff Semantics

## Context
`Murder_at_the_Drowning_Lass` showed that toolkit finishing can succeed structurally while still lacking module-local monster media. In that state:
- monster materialization succeeded
- schema validation was green
- semantic authority had no blocking findings
- only media debt remained

The current finisher semantics collapse that case into an overall failed result. Product policy says this should instead be a successful build with explicit next-step guidance to `Module Builder -> Module Media Generator`.

## Goals
- Separate media-only debt from true build failure in toolkit finisher results.
- Preserve explicit media debt reporting.
- Make the post-build next step operator-facing and actionable.

## Non-Goals
- Automatic media generation from the finisher.
- Gameplay/readiness payload normalization.
- Toolkit UI reordering.
- Broad readiness or publishability redesign.

## Decisions

### Decision: Toolkit finisher SHALL support success-with-handoff semantics
When structural build stages are green and the remaining blocker is module media debt, the finisher SHALL report a successful build outcome plus explicit handoff metadata.

### Decision: Manual remediation path SHALL be Module Builder -> Module Media Generator
The finisher SHALL route users to `Module Builder -> Module Media Generator` as the primary remediation path for missing module monster/NPC media.

### Decision: True structural failures SHALL remain failures
If continuity, registry, semantic authority, materialization, or non-media finishing blockers fail, the finisher SHALL preserve failed outcome semantics.

## Architecture
- Adjust toolkit finisher result interpretation after publishability/readiness results are available.
- Detect the narrow case where media debt remains but structural build stages succeeded.
- Add explicit payload/report fields for handoff messaging without forcing broad status renames if a compatibility-safe additive field is sufficient.

## Risks / Trade-offs
- Over-broad success interpretation could hide real failures; detection must stay narrow and testable.
- Too much status churn could break downstream consumers; additive fields are preferred where possible.

## Migration Plan
1. Define the finisher outcome boundary for media-only debt.
2. Implement bounded success-with-handoff semantics in `web/extensions/toolkit_module_finisher.py`.
3. Add targeted regression coverage.
4. Verify with a real toolkit media-debt case.

## Verification Plan
- `python3 -m py_compile web/extensions/toolkit_module_finisher.py`
- Run targeted finisher/build-result tests.
- Exercise a real toolkit case such as `Murder_at_the_Drowning_Lass` and confirm:
  - build completes
  - media debt remains explicit
  - handoff path points to `Module Builder -> Module Media Generator`

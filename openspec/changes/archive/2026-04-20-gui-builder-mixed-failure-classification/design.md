# Design: GUI Builder Mixed Failure Classification

## Context
`gui-builder-media-handoff-semantics` establishes success-with-media-handoff for pure media-only debt. Real module payloads can still include true semantic blockers at the same time. If finisher logic collapses those mixed cases into the media-only path, the GUI will mislead operators and hide real authoring defects behind an incorrect success outcome.

## Goals
- Define a deterministic mixed-failure contract after payload normalization is correct.
- Preserve success-with-media-handoff only for pure media-only debt.
- Keep mixed semantic/content failures explicit and operator-actionable.

## Non-Goals
- UI tab ordering changes.
- Gameplay/readiness payload normalization.
- LLM-assisted semantic repair.
- Automatic semantic remediation.

## Decisions

### Decision: Media-only handoff SHALL require semantic-clean publishability state
Success-with-media-handoff SHALL apply only when readiness/build state is otherwise structurally green and semantic publishability is free of non-media blockers.

### Decision: Mixed cases SHALL remain failed
When media debt and semantic/content blockers coexist, finisher output SHALL remain failed and SHALL expose both classes clearly enough for operator routing.

### Decision: Classification SHALL remain deterministic
The slice SHALL use existing publishability/reporting signals and SHALL NOT introduce LLM classification or heuristic narrative repair.

## Architecture
- Tighten post-publishability classification in `web/extensions/toolkit_module_finisher.py` to require a pure media-only profile before success-with-handoff is allowed.
- Ensure `scripts/audit_module_publishability.py` exposes enough structured distinction for tests and finisher consumers.
- Add focused regression coverage for:
  - pure media-only debt
  - mixed media + semantic failure
  - semantic-only failure

## Risks / Trade-offs
- Over-collapsing to failed status could regress the new handoff behavior if media-only detection is too strict.
- Under-classifying semantic blockers would recreate the current product mismatch. Tests should pin the boundary tightly.

## Migration Plan
1. Define the mixed-failure boundary from real payload evidence.
2. Tighten finisher/publishability classification logic.
3. Add focused regression coverage.
4. Verify against a mixed real-module example.

## Verification Plan
- `python3 -m py_compile web/extensions/toolkit_module_finisher.py scripts/audit_module_publishability.py`
- Run targeted finisher/publishability tests.
- Show one concrete mixed-case payload example that remains failed while preserving media debt details.

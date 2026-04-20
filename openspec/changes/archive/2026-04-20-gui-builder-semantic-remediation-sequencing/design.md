# Design: GUI Builder Semantic Remediation Sequencing

## Context
The uploader now has a clearer deterministic boundary:
- media-only debt can be handed off cleanly
- gameplay/readiness payload shape can be normalized deterministically
- mixed failures can remain failed explicitly

After those land, unresolved destination aliases and similar semantic blockers become the next bounded problem. They are not solvable by report-shape fixes alone, but they also should not be widened immediately into broad autonomous LLM repair.

## Goals
- Define the bounded builder-facing sequence for semantic remediation work.
- Separate semantic authoring defects from media debt and reporting defects.
- Prepare a stable on-ramp for later reviewable builder assistance.

## Non-Goals
- Implementing the full semantic repair engine.
- Broad autonomous LLM fixing.
- Revisiting media-only handoff or UI ordering.

## Decisions

### Decision: Semantic remediation SHALL begin only after deterministic reporting is stable
The builder sequence SHALL treat semantic remediation as the next stage after media-handoff semantics, UI ordering, payload normalization, and mixed-failure classification are all explicit.

### Decision: Semantic blockers SHALL remain explicit authoring defects
Unresolved destination aliases and similar blockers SHALL be surfaced as builder remediation work, not silently repaired by the runtime.

### Decision: Future builder assistance SHALL stay reviewable
Any future builder-side proposal generation SHALL preserve reviewability and Python authority over final publishability state.

## Architecture
- Define a builder-facing remediation sequence that names the operator-visible handoff after deterministic failure classification.
- Identify the small set of semantic blocker classes that should feed the first semantic remediation slice.
- Keep this slice artifact-focused so later implementation changes start from an explicit contract.

## Risks / Trade-offs
- If this remains too vague, later Phase 2 work may sprawl again into mixed reporting and semantic policy.
- If it is too prescriptive too early, it may pre-commit implementation details before the deterministic chain is complete.

## Migration Plan
1. Capture the deterministic preconditions for semantic remediation.
2. Define the first semantic blocker classes and the builder-facing sequence.
3. Produce builder review guidance for the next execution slice.

## Verification Plan
- Confirm the rollout sequence explicitly places this slice after the deterministic GUI-builder fixes.
- Produce a builder-facing prompt that scopes the first semantic remediation slice.
- Show how a known unresolved destination-alias blocker would enter that sequence.

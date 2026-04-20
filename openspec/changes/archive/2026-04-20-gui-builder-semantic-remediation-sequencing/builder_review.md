# GUI Builder Semantic Remediation Sequencing

## Builder Review Draft

Purpose: define the next builder-facing planning slice after the deterministic GUI-builder fixes so semantic authoring defects are handled explicitly and reviewably.

This is not approval to start broad autonomous repair.

## Intent

The uploader roadmap now has a clean deterministic chain:

1. media-only handoff semantics
2. workflow UI ordering
3. gameplay/readiness payload normalization
4. mixed-failure classification

After those land, unresolved destination aliases and similar publishability blockers become a distinct semantic remediation stage.

## Evidence Baseline

- `The_Ancients_Lab` showed a real unresolved destination phrase blocker (`crucible hall`) alongside media debt.
- That blocker is not a payload bug.
- It should not be silently collapsed into media handoff or hidden inside Phase 2 ambiguity work.

## MUST Contract

- The builder SHALL keep this slice planning-focused and builder-facing.
- The builder SHALL define semantic remediation as a stage after the deterministic GUI-builder fixes.
- The builder SHALL preserve Python authority over final readiness/publishability state.
- The builder SHALL keep future builder assistance reviewable.
- The builder SHALL NOT implement broad autonomous semantic repair in this slice.

## SHOULD Guidance

- Prefer naming a small first set of semantic blocker classes, starting with unresolved destination aliases.
- Prefer explicit operator workflow language over abstract architecture language.
- Keep the outcome ready to hand to a later builder implementation slice.

## Proposed Step Sequence

### Step 1 - Lock the sequencing boundary

Document that semantic remediation begins only after the deterministic GUI-builder fixes are complete.

### Step 2 - Define the first semantic remediation lane

Identify the first blocker classes and how they surface in the builder workflow.

### Step 3 - Produce the builder-facing next-step contract

Create the prompt/review artifact that a later builder implementation slice can use without reopening the reporting-policy questions.

## Full Builder Prompt

Implement OpenSpec draft `gui-builder-semantic-remediation-sequencing` as a planning-only builder artifact pass.

Goal: define the explicit post-deterministic semantic remediation sequence so unresolved destination-alias and similar authoring defects are handled in a later bounded builder slice rather than mixed with media/reporting work.

Allowed files:

- this change's planning artifacts
- roadmap docs if needed for sequencing parity

Forbidden:

- implementation of semantic repair runtime behavior
- LLM autonomy widening
- reopening UI ordering or media-handoff semantics scope

Required:

- explicit sequencing after the deterministic GUI-builder chain
- first semantic blocker classes identified
- builder-facing next-step prompt/review guidance
- one concrete blocker example in sequence

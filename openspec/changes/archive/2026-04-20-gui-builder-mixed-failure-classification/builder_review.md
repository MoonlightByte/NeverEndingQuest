# GUI Builder Mixed Failure Classification

## Builder Review Draft

Purpose: define the bounded deterministic slice that separates pure media-only handoff from mixed publishability failure after the new media-handoff semantics land.

This is a builder-facing review artifact for status policy only.

## Intent

The next slice SHALL codify one product boundary made visible by `The_Ancients_Lab`:

1. some modules are pure media-only debt and should complete with explicit handoff
2. some modules are mixed failures because media debt exists alongside true semantic/content blockers
3. the second class must remain failed

## Evidence Baseline

- `gui-builder-media-handoff-semantics` intentionally covers only the pure media-only case.
- `The_Ancients_Lab` payload showed:
  - missing monster-media debt in gameplay/readiness
  - unresolved destination phrase blocker (`crucible hall`) in semantic publishability
  - overall status correctly should remain failed until the semantic blocker is repaired.

## MUST Contract

- The builder SHALL keep scope limited to deterministic finisher/publishability classification.
- The builder SHALL preserve success-with-media-handoff for pure media-only debt.
- The builder SHALL keep mixed media-plus-semantic cases failed.
- The builder SHALL preserve explicit media debt visibility even when the overall status remains failed.
- The builder SHALL NOT introduce LLM remediation or UI ordering work in this slice.

## SHOULD Guidance

- Prefer using existing structured publishability fields rather than inventing broad new status trees.
- Keep the distinction test-first and easy for finisher consumers to read.
- Keep operator output explicit about why the build remains failed.

## Proposed Step Sequence

### Step 1 - Define the boundary

Codify the difference between:

- pure media-only debt
- mixed media + semantic/content blockers
- semantic/content blockers without media debt

### Step 2 - Tighten deterministic classification

Apply the boundary in finisher/reporting code so only the first case can return success-with-media-handoff.

### Step 3 - Add focused regression coverage

Prove all three cases are classified correctly.

### Step 4 - Verify against a real mixed case

Use `The_Ancients_Lab`-style evidence to confirm the build remains failed while still exposing media debt.

## Full Builder Prompt

Implement OpenSpec draft `gui-builder-mixed-failure-classification` Step 1-4 only.

Goal: keep success-with-media-handoff limited to pure media-only debt and preserve failed semantics for mixed media plus semantic/content blockers.

Allowed files:

- `web/extensions/toolkit_module_finisher.py`
- `scripts/audit_module_publishability.py`
- targeted finisher/publishability tests

Forbidden:

- gameplay/readiness payload normalization work
- toolkit UI ordering work
- LLM-assisted semantic repair
- broad uploader redesign

Required:

- deterministic mixed-failure boundary
- explicit failed semantics for mixed cases
- preserved media debt visibility in mixed-case output
- focused regression coverage
- one real mixed-case verification example

Verification:

- `python3 -m py_compile web/extensions/toolkit_module_finisher.py scripts/audit_module_publishability.py`
- run targeted finisher/publishability tests
- capture one mixed-case report example

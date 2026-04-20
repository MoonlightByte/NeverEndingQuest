# GUI Builder Numillian Post-Reingest Gate Reconciliation

## Builder Review Draft

Purpose: define the next bounded OpenSpec execution slice after the successful Numillian structural reconciliation and re-ingest proving run.

This is a builder-facing review artifact, not approval to start Phase 2.

## Intent

The next slice SHALL reconcile the two remaining post-reingest gate blockers for `The_Hidden_City_of_Numillian`:

1. gameplay gate failure caused by missing base monster media for structurally-authored combatants
2. semantic-authority output that still needs to classify the single unresolved player-facing destination phrase `paradox sanctuary` as explicit Phase 2 ambiguity debt

The next slice SHALL NOT start broad LLM-assisted classification work.
Phase 2 remains deferred, and this slice SHALL treat `paradox sanctuary` as deferred ambiguity rather than attempting broader deterministic closure.

## Evidence Baseline

- Monster hydration/materialization succeeded in finisher.
- Schema validation passed cleanly for the module.
- Spatial contract and map/area parity passed cleanly.
- Hidden-NPC probe precision passed.
- Remaining failures are:
  - gameplay gate strict blocking on missing base monster media
  - semantic audit/probe handling for unresolved destination phrase `paradox sanctuary`
- Existing toolkit manual media-generation surfaces already exist and are the approved operator remediation path.

## MUST Contract

- The builder SHALL keep scope limited to:
  - gameplay media gating/reporting policy for toolkit finisher and publishability surfaces
  - explicit deferred-ambiguity handling of `paradox sanctuary`
  - tests and reporting needed to prove those changes
- The builder SHALL NOT widen Phase 2 LLM integration in this slice.
- The builder SHALL preserve existing strict schema validation and monster materialization behavior.
- The builder SHALL preserve hidden-NPC precision behavior.
- The builder SHALL keep Python/mechanical truth authoritative.
- The builder SHALL keep ambiguous narrative interpretation bounded and explicit.
- The builder SHALL NOT add automatic provider image generation to toolkit finisher.
- The builder SHALL point missing toolkit monster media outcomes to the existing manual toolkit monster-image generation workflow.
- The builder SHALL classify `paradox sanctuary` as explicit Phase 2 ambiguity debt rather than silently broadening extraction heuristics.

## SHOULD Guidance

- Prefer the smallest policy/contract change that makes finisher outcomes interpretable.
- Prefer additive classification/reporting over broad behavioral rewrites.
- Keep gameplay media blocking strict, but make the report clearer and operator-actionable.
- Reuse existing toolkit manual media-generation surfaces instead of duplicating automation in the finisher.

## Proposed Step Sequence

### Step 1 - Lock the approved policy boundary

Encode the already approved policy in OpenSpec and builder-facing execution text:

- missing base monster media remains publishability-blocking
- toolkit finisher SHALL NOT auto-run provider generation
- existing toolkit manual monster-image generation surfaces are the remediation path

This step SHALL end with one explicit contract decision reflected in code-facing planning text.

### Step 2 - Reconcile gameplay media gate behavior

Implement the approved policy for toolkit finisher/readiness/publishability integration.

Valid outcome:

- keep strict publishability blocking and improve surfaced diagnostics so reports explicitly route operators to the existing toolkit manual monster-image workflow

This step SHALL NOT make structurally-authored combatants silently pass without an explicit contract.

### Step 3 - Reconcile the destination alias boundary

Address the unresolved phrase `paradox sanctuary` by explicit classification/reporting as deferred Phase 2 ambiguity debt.

This step SHALL NOT reopen broad destination extraction from evocative prose.

### Step 4 - Verify with a fresh Numillian finisher run

Re-run the toolkit finisher/publishability path for `The_Hidden_City_of_Numillian` and capture the exact remaining outcome.

Acceptance target:

- gameplay media result is explicit and policy-consistent
- missing media outcomes point to the existing manual toolkit image workflow
- `paradox sanctuary` no longer appears as an unclassified misleading structural failure
- remaining failures, if any, are clearly true media debt or clearly deferred ambiguity debt

## Full Builder Prompt

Implement OpenSpec draft `gui-builder-numillian-postreingest-gate-reconciliation` Step 1-4 only.

Goal: reconcile the two remaining post-reingest Numillian gate blockers without starting Phase 2 LLM integration, while preserving manual toolkit monster-image generation as the remediation path.

Allowed files:

- `scripts/audit_module_gameplay.py`
- `scripts/audit_module_readiness.py`
- `scripts/audit_module_publishability.py`
- `utils/module_semantic_authority.py`
- `scripts/module_semantic_authority_audit.py`
- `scripts/module_semantic_probe_harness.py`
- targeted tests covering those paths
- reporting artifact docs if needed

Forbidden:

- broad LLM-routing/classification additions
- widening prose-mining heuristics across unrelated fields
- weakening schema validation, monster materialization, or hidden-NPC probe contracts
- adding finisher automation that duplicates existing toolkit image-generation surfaces
- unrelated uploader/UI changes

Required:

- make the gameplay media-policy outcome explicit for toolkit finisher and point unresolved cases to the existing manual toolkit monster-image generation workflow
- classify `paradox sanctuary` as deferred Phase 2 ambiguity debt without a misleading structural fail signal
- add or update regression tests for both behaviors
- prove the result with a fresh Numillian finisher/readiness/publishability run

Edit Strategy: Apply one anchored patch at a time, then re-run `py_compile` before the next patch.

Verification:

- `python3 -m py_compile scripts/audit_module_gameplay.py scripts/audit_module_readiness.py scripts/audit_module_publishability.py utils/module_semantic_authority.py scripts/module_semantic_authority_audit.py scripts/module_semantic_probe_harness.py`
- run targeted tests for gameplay/media and semantic authority/probes
- run the real Numillian finisher/readiness/publishability flow again and capture the post-change result

Output:

- summary of contract decision for media gating and manual remediation path
- summary of exact `paradox sanctuary` deferred-ambiguity handling
- list of files changed
- test/validation commands and outcomes
- residual blockers, if any

## Review Questions

1. Does the builder prompt clearly preserve the approved policy that toolkit image generation remains manual/operator-invoked?
2. Does the prompt clearly encode `paradox sanctuary` as Phase 2 ambiguity debt rather than asking the builder to solve it deterministically now?
3. Do you want this builder draft kept as the primary review artifact, or also mirrored into a more compact step-only prompt file?

## Overview

This change adds a bounded readiness convergence layer to the toolkit/module repair workflow. The core problem is no longer missing pipeline stages; it is that the existing repair loop reaches a stable blocker set and has no rule for distinguishing "needs another pass" from "current repair coverage is exhausted."

The design therefore separates three states:

1. **Repairable progress**: a pass changes files or reduces the blocker set.
2. **Fixed-point non-convergence**: consecutive passes produce the same blocker signature.
3. **Residual content debt**: remaining blockers are valid but outside deterministic repair scope.

The implementation should improve deterministic repair coverage for the known Numillian blocker families while keeping validator truth strict.

## Goals

- Detect fixed-point repair loops deterministically.
- Add concrete repairers for the four current residual blocker classes.
- Preserve strict validator semantics: unresolved blockers still fail readiness.
- Surface convergence outcomes in machine-readable artifacts.
- Use Numillian as the first canary to prove readiness can progress past schema gate.

## Non-Goals

- No LLM-assisted repair or classification.
- No relaxation of gameplay/media requirements for real monsters.
- No attempt to make legacy watcher-built modules pass toolkit provenance.
- No change to the existing semantic warning-only publishability policy except for reporting continuity.

## Architecture

### 1. Convergence Signature

The repair workflow should compute a deterministic blocker signature after each validation pass.

The signature SHOULD include:
- validator family/category,
- normalized location/plot/monster target,
- expected file or object path,
- stable failure reason.

The convergence controller MUST compare the current signature with the previous pass.

Rules:
- If the signature changes, another pass MAY run within budget.
- If the signature is identical across two consecutive passes, the workflow MUST stop and classify the result as fixed-point non-convergence.
- The workflow MUST NOT keep retrying identical blocker sets just because budget remains.

### 2. Repair Coverage Matrix

The workflow should explicitly map validator families to deterministic repairers.

Initial required matrix:

1. **Monster schema completion**
   - Input: existing generated/hydrated monster JSON missing required schema fields.
   - Repair path: backfill required fields from bestiary seed, generated payload, or deterministic defaults only when source-of-truth is clear.
   - Failure mode: if required fields cannot be derived safely, classify as residual monster-schema debt.

2. **Monster reference closure**
   - Input: area/location monster reference resolves to no module monster file.
   - Repair path: reuse existing materialization/closure helpers to generate or hydrate the missing file.
   - Failure mode: classify as unresolved monster-reference debt with expected path.

3. **Plot prerequisite repair**
   - Input: finale/conclusion plot point missing explicit prerequisite for known upstream dependency.
   - Repair path: deterministic insertion of prerequisite gate when upstream chain is uniquely provable.
   - Failure mode: classify as residual plot-gating debt when dependency chain is ambiguous.

4. **Spatial adjacency convergence**
   - Input: connected rooms remain non-cardinally adjacent after earlier remediation.
   - Repair path: rerun shared spatial planner using authored connectivity as truth and rewrite coordinates/directions consistently.
   - Failure mode: classify as residual spatial contradiction when authored graph cannot be represented without unsafe mutation.

### 3. Reporting Model

The readiness workflow should emit convergence-aware artifacts.

Minimum output fields:
- `status`
- `ready_for_finishing`
- `deterministic_passes`
- `fixed_point_detected`
- `blocker_signature`
- `residual_blocker_classes`
- `repair_actions`
- `canary_module` when applicable

These fields SHOULD be included in JSON reports used by toolkit rerun/canary workflows so operators can tell whether a module failed because of missing repair coverage or true post-repair content debt.

### 4. Numillian Canary Workflow

Numillian should remain the primary canary for this slice because:
- hydration is already healthy there,
- provenance/publishability policy work is already separated,
- the remaining blockers are concentrated in four deterministic structural families.

The canary should be considered successful when:
- readiness progresses beyond the current schema-gate fixed point,
- the workflow no longer ends with `repair_budget_exhausted` on an unchanged blocker set,
- and any remaining failures are clearly classified as residual content debt rather than convergence failure.

## Risks And Mitigations

### Risk: Unsafe deterministic mutation

Repairers could overcorrect authored content.

Mitigation:
- MUST repair only when the source-of-truth is unique and deterministic.
- SHOULD classify and stop when ambiguity remains.

### Risk: Hidden retry loops remain

The loop could still keep running if signatures are unstable.

Mitigation:
- MUST normalize blocker signatures before comparison.
- SHOULD include stable path + category + reason components only.

### Risk: Reporting becomes noisy

Additional state could overwhelm operators.

Mitigation:
- MUST keep the contract machine-readable and compact.
- SHOULD summarize blocker classes rather than dumping duplicate raw errors.

## Rollout

1. Add convergence signature and stop rules.
2. Add targeted repairers for the four known blocker families.
3. Extend report payloads and tests.
4. Re-run Numillian as canary.
5. Persist updated rerun artifact(s) for operator review.

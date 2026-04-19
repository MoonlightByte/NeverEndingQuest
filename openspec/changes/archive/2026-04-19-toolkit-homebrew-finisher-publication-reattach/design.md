## Overview

This slice consumes the uploader boundary established by the previous changes:

1. source upload and artifact workspace exist,
2. normalization and review are complete,
3. packet-driven build is complete,
4. structural readiness has already either failed boundedly or reached `ready_for_finishing`,
5. repeated uploads can rebuild cleanly.

The only new responsibility here is to take jobs that are already `ready_for_finishing` and route them through the same finisher/publication stack used by developer ingest.

## Goals

- MUST attach the existing finisher/publication stack after readiness, not before.
- MUST require `ready_for_finishing` as the only successful entry state for upload finishing.
- MUST preserve the distinction between:
  - `build_completed`
  - `ready_for_finishing`
  - `completed`
- MUST require `publishable_status=pass` before final registry integration.
- MUST preserve finisher/report artifact parity with the developer ingest path where practical.
- MUST surface finisher/publication outcomes in upload job status and UI.
- SHOULD reuse shared helpers instead of branching developer and upload publication logic.

## Non-Goals

- Do not change normalization contracts.
- Do not change packet build behavior.
- Do not redesign readiness repair.
- Do not add inline metadata editing.
- Do not modify concept-builder orchestration.

## Entry Contract

Upload finishing may begin only when all of the following are true:

1. job state is `ready_for_finishing`
2. build artifact workspace exists
3. module slug is known
4. readiness reports/artifacts exist or are derivable from the readiness stage

If any of these are false, the job MUST fail closed and stay outside publication.

## State Model

Recommended upload states for this slice:

1. `ready_for_finishing`
2. `finishing`
3. `publishability_audit`
4. `completed`
5. `finishing_failed`
6. `not_publishable`

Interpretation:

- `ready_for_finishing`: structural gate passed; safe to enter shared finisher
- `finishing`: shared finisher work in progress
- `publishability_audit`: finisher complete enough to evaluate publishability outcome
- `completed`: finisher succeeded and `publishable_status=pass`
- `finishing_failed`: shared finisher/runtime defect or hard fail prevented completion
- `not_publishable`: finisher ran, but final publication gate remained red

## Orchestration

Recommended path:

1. upload job reaches `ready_for_finishing`
2. route starts finisher worker
3. finisher worker invokes shared toolkit finisher/publication stack
4. shared stack returns structured outcome containing at least:
   - `ready_status`
   - `publishable_status`
   - final report payloads/paths
5. route maps outcome into terminal upload state

Mapping:

- `ready_status=pass` and `publishable_status=pass` -> `completed`
- `ready_status=pass` and `publishable_status!=pass` -> `not_publishable`
- finisher exception or hard failure -> `finishing_failed`

## Reporting Contract

The upload UI/reporting surface should make these distinctions visible:

1. structurally ready but not yet finished
2. finisher running
3. publishability audit running
4. finished and publishable
5. finished but not publishable
6. finisher/system failure

Persisted artifacts should include, at minimum:

1. finishing report
2. publishability summary or final finisher payload
3. upload job terminal summary with final gate outcomes

## Shared-Service Rule

The uploader MUST compose the existing finisher/publication system. If orchestration wrappers are needed, they should be thin adapters that:

1. translate upload job context into finisher inputs
2. persist upload-facing report metadata
3. avoid duplicating developer-ingest publication logic

## Risks

- Shared finisher drift: mitigate by reusing the same finisher surface and matching reports.
- State ambiguity: mitigate by adding explicit `finishing` and `not_publishable` states.
- Premature registry integration: mitigate by hard-gating on `publishable_status=pass` only.
- Upload/dev divergence: mitigate with parity tests against representative modules.

## Implementation Sketch

1. Extend upload job state machine to add finisher/publication states.
2. Add route worker that consumes `ready_for_finishing` only.
3. Attach shared finisher and map its outcome to upload states.
4. Persist finisher/publication artifacts to the upload workspace/job payload.
5. Update toolkit UI to show finisher/publication progress and outcomes.
6. Add parity/regression tests.

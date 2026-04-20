# GUI Builder Media Handoff Semantics

## Builder Review Draft

Purpose: define the next bounded OpenSpec execution slice that corrects toolkit finisher semantics for post-build media debt without adding automation that bypasses the existing manual media workflow.

This is a builder-facing review artifact, not approval to start broader LLM-assisted finishing work.

## Intent

The next slice SHALL reconcile a narrow product-contract mismatch:

1. toolkit finisher currently reports an overall failed build when JSON/materialization/schema/semantic gates are green but module monster/NPC media is still missing
2. product policy now says this outcome should be a successful build plus explicit handoff to `Module Builder -> Module Media Generator`

The next slice SHALL NOT add automatic media generation to the finisher.

## Evidence Baseline

- `web/extensions/toolkit_module_finisher.py` runs continuity, semantic authority, registry, monster materialization, then publishability.
- `_run_publishability_stage(...)` currently feeds readiness/publishability failure into the finisher result.
- `Murder_at_the_Drowning_Lass` proved the mismatch clearly:
  - monster materialization succeeded
  - schema was green (`62 passed`, `0 failed`)
  - semantic authority had no blocking findings
  - semantic probes were only degraded by `handoff_probe_fixture_missing`
  - gameplay/readiness failed because structurally-authored monsters lacked module-local base media
- Approved product policy is: do not fail the otherwise successful toolkit build for this case; instead report the debt and direct the user to `Module Builder -> Module Media Generator`.

## MUST Contract

- The builder SHALL keep scope limited to toolkit finisher/build-result semantics and post-build media handoff messaging.
- The builder SHALL preserve existing monster hydration/materialization behavior.
- The builder SHALL preserve schema, semantic authority, semantic probe, and readiness execution logic except where required to reinterpret post-build media debt for toolkit finisher outcome reporting.
- The builder SHALL NOT add automatic provider image generation.
- The builder SHALL NOT route users to monster/NPC manager tabs as the primary post-build remediation path for this slice.
- The builder SHALL route the user to `Module Builder -> Module Media Generator` when a toolkit build is otherwise successful but module monster/NPC media is still missing.
- The builder SHALL keep the missing media debt explicit in the returned payload/report.
- The builder SHALL distinguish true build failure from post-build media handoff debt in a deterministic, testable way.

## SHOULD Guidance

- Prefer the smallest host-file change in `web/extensions/toolkit_module_finisher.py` that cleanly separates build success from media-debt follow-up.
- Prefer additive payload fields over changing many existing status names if one compatibility-safe field can carry the handoff semantics.
- Keep the wording operator-facing and actionable.
- Keep the slice independent from UI reordering and gameplay/readiness payload-shape normalization except for the minimum payload fields needed by the finisher response.

## Proposed Step Sequence

### Step 1 - Define the finisher outcome boundary

Codify the exact contract for toolkit builds:

- if structural build stages are green and only module media debt remains, the build outcome SHALL be success-with-handoff, not failure
- the payload SHALL preserve the media debt details
- the payload SHALL name `Module Builder -> Module Media Generator` as the next action

### Step 2 - Implement bounded finisher semantics

Apply the contract in the toolkit finisher path.

Valid outcome:

- true structural failures still fail
- media-only debt does not mark the overall build as failed
- returned report clearly says build completed and media generation remains a manual next step

### Step 3 - Add targeted regression coverage

Add or update tests that prove:

- media-only debt produces successful build handoff semantics
- structural failures still fail
- returned payload includes the correct handoff path

### Step 4 - Verify against a real toolkit case

Use a real module case such as `Murder_at_the_Drowning_Lass` to confirm the post-build outcome now matches product policy.

Acceptance target:

- build completes
- media debt remains visible
- user is directed to `Module Builder -> Module Media Generator`
- no provider automation is introduced

## Full Builder Prompt

Implement OpenSpec draft `gui-builder-media-handoff-semantics` Step 1-4 only.

Goal: change toolkit finisher semantics so otherwise successful module builds do not fail on missing module monster/NPC media and instead return an explicit post-build handoff to `Module Builder -> Module Media Generator`.

Allowed files:

- `web/extensions/toolkit_module_finisher.py`
- targeted tests for finisher/build-result behavior
- report artifact docs only if needed for verification output

Forbidden:

- automatic media generation from finisher
- broad readiness/publishability redesign
- UI tab ordering changes
- gameplay/readiness payload normalization work beyond the minimum data plumbing the finisher directly needs
- unrelated uploader changes

Required:

- define a deterministic success-with-handoff outcome for media-only debt
- preserve true failure semantics for structural/build blockers
- include explicit next-step guidance to `Module Builder -> Module Media Generator`
- add regression coverage
- verify against a real toolkit build case

Edit Strategy: Apply one anchored patch at a time, then re-run `py_compile` before the next patch.

Verification:

- `python3 -m py_compile web/extensions/toolkit_module_finisher.py`
- run targeted finisher/build-result tests
- run the real toolkit finisher flow for a media-debt module and capture the result

Output:

- exact finisher outcome contract implemented
- files changed
- validation/test commands and outcomes
- example post-build handoff payload fields
- residual blockers, if any

## Review Questions

1. Does this slice keep the policy narrow enough: finish successfully, then hand off to `Module Builder -> Module Media Generator`?
2. Should the build outcome wording use a new explicit status (for example `success_with_media_handoff`) or preserve `success` and carry the handoff in separate fields/messages?
3. Do you want this slice kept completely isolated from readiness/publishability normalization, or is minimal shared payload plumbing acceptable if needed?

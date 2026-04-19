## Overview

This change operationalizes Phase 8 from `plans/module-uploader.md` by turning a tracked representative Homebrewery corpus into a repeatable acceptance gate.

The intent is not to redesign uploader architecture. The intent is to prove that the already-implemented architecture remains reliable across representative sources and produces bounded, operator-actionable outcomes.

## Goals

- MUST define a deterministic corpus fixture list used by automated and manual checks.
- MUST source the canonical acceptance corpus from tracked in-repo fixtures only.
- MUST cover at least one clean success path and one bounded blocked/failure path.
- MUST validate normalization output shape and review packet generation.
- MUST validate build/readiness progression and finishing/publication terminal outcomes.
- MUST add parity checks against developer ingest outcomes for representative fixtures.
- MUST NOT hardcode developer-local directories or private corpus paths anywhere in committed artifacts.
- SHOULD keep tests practical by using existing mocks/stubs where full end-to-end execution is expensive.

## Non-Goals

- Do not redesign uploader route orchestration.
- Do not redesign finisher/publication semantics.
- Do not add gameplay runtime behavior.
- Do not broaden rights/provenance policy in this slice.
- Do not depend on developer-specific local folders as the acceptance corpus source.

## Corpus Fixture Contract

Canonical fixture policy:

1. The baseline acceptance corpus MUST live in a tracked repo-owned fixture directory.
2. Fixture names may mirror representative Homebrewery sources, but the committed gate depends only on tracked fixtures.
3. Optional extended corpus inputs MAY be supported through explicit operator-supplied CLI/config paths.
4. No default external path may be hardcoded.

The suite MUST remain fully runnable from tracked repository contents alone.

## Acceptance Model

For each runnable fixture, classify outcome as:

1. `publishable_pass`
2. `not_publishable_bounded`
3. `finishing_failed_bounded`
4. `quarantined_bounded`

Any unclassified hard error is gate-fail.

## Parity Rule

Representative fixture runs must show parity at the contract level between:

1. developer ingest finishing outcomes (`ready_status`, `publishable_status`), and
2. public upload finishing outcomes (`completed` vs `not_publishable` vs `finishing_failed`).

Exact byte-for-byte report parity is not required, but status mapping and blocker class semantics MUST align.

## Testing Surfaces

1. Snapshot tests: normalized packet/review-summary contract fields present and stable.
2. Upload route regression extension: fixture-driven status progression assertions.
3. Parity tests: shared finisher result mapping consistency.
4. Manual smoke script: one-command run for operator sign-off.
5. Optional external-corpus mode: explicit operator path only, with graceful skip/reporting when absent.

## Reporting

Produce a bounded corpus summary report with:

1. fixtures attempted,
2. fixtures skipped and reason,
3. terminal outcome class per fixture,
4. parity pass/fail,
5. overall gate status.

## Risks

- Missing optional external corpus files: mitigate with explicit skip reporting and a tracked in-repo baseline corpus.
- Test flakiness from heavyweight steps: mitigate with deterministic mocks for contract checks and narrow live smokes.
- Parity drift over time: mitigate with explicit status-mapping assertions.

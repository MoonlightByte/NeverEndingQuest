# toolkit-semantic-shortform-destination-normalization

## Why

`Murder_at_the_Drowning_Lass` is currently blocked by unresolved destination phrases that are already semantically knowable from the same authored payload.

- `oath chamber` remains unresolved while `silent oath chamber` already resolves to `H03`
- `remnant sanctuary` remains unresolved while `serpents remnant sanctuary` already resolves to `H01`

This is not a media-handoff problem and it is not a later LLM-builder problem. It is deterministic semantic normalization debt in the current Python authority path. Until that debt is fixed, modules that should fall through to `Module Builder -> Module Media Generator` remain trapped in mixed-failure status because short-form aliases are still classified as semantic publishability blockers.

## What Changes

### New Capabilities

- Define deterministic short-form destination normalization against already-resolved authored aliases in the same module semantic payload.
- Define a publishability/reporting boundary where deterministically collapsed short-form aliases no longer remain semantic blockers.

### Modified Capabilities

- `module-semantic-authority-enrichment` SHALL preserve explicit ambiguity diagnostics, but SHALL collapse uniquely knowable short-form destination phrases when an already-resolved authored alias provides a deterministic anchor.
- `module-publishability-reporting` SHALL distinguish true semantic blockers from short-form alias debt that has already been deterministically normalized.
- `toolkit-module-postbuild-finishing` SHALL preserve the existing media-only vs mixed-failure contract, but SHALL allow media handoff semantics to surface once short-form semantic blocker debt has been normalized away.

## Capability Scope

### MUST

- The implementation SHALL remain deterministic and Python-authoritative.
- The implementation SHALL only normalize unresolved short-form destination phrases when exactly one already-resolved authored alias in the same module provides a strong canonical anchor.
- Truly ambiguous short forms SHALL remain semantic publishability blockers.
- The change SHALL preserve the existing rule that mixed media plus true semantic blockers remain failed.
- The change SHALL include regression coverage using `Murder_at_the_Drowning_Lass` and at least one ambiguous counterexample.

### SHOULD

- Reporting should preserve provenance showing which resolved authored alias supplied the normalization anchor.
- Toolkit-facing reports should make it clear when a former blocker was normalized rather than silently disappearing.

## Non-Goals

- Broad LLM-assisted semantic remediation.
- General freeform prose destination mining.
- Changing the media-only handoff contract.
- Reclassifying truly ambiguous aliases as non-blocking.

## Impact

- Affected code:
  - likely semantic-authority enrichment helpers and authority audit paths
  - publishability classification/reporting helpers
  - targeted finisher and semantic regression tests
- Affected workflows:
  - toolkit post-build semantic enrichment
  - publishability blocker classification
  - media handoff eligibility for semantically normalized modules
- Primary canary module:
  - `modules/Murder_at_the_Drowning_Lass`

## Risks

- Over-normalization could incorrectly collapse truly distinct authored locations.
- Under-normalization would preserve the current false mixed-failure state.
- Silent normalization without provenance could make future semantic audits harder to debug.

## Fallback

- If unique normalization cannot be proven from already-resolved authored aliases, preserve the current unresolved blocker state.
- If reporting cannot surface normalized provenance cleanly, preserve correctness first and keep the phrase non-blocking only when the deterministic collapse is still explicit in the payload.

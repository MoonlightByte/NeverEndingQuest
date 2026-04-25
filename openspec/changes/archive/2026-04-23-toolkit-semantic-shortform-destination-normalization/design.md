# Design: toolkit-semantic-shortform-destination-normalization

## Context

The current semantic-authority pipeline already knows enough to resolve some destination phrases, but it still leaves shorter player-facing variants unresolved even when a longer authored alias has already been resolved to one canonical location.

`Murder_at_the_Drowning_Lass` demonstrates the failure mode clearly:
- `silent oath chamber` -> `H03` is resolved
- `oath chamber` remains unresolved
- `serpents remnant sanctuary` -> `H01` is resolved
- `remnant sanctuary` remains unresolved

That residual unresolved state propagates into publishability reporting as semantic blocker debt. Because the same report also carries expected manual monster-media debt, the finisher correctly classifies the result as mixed failure. The bad outcome is therefore caused upstream: the short-form phrases should have been deterministically normalized before publishability classification.

## Goals

- Normalize uniquely knowable short-form destination phrases deterministically.
- Preserve true ambiguity as a semantic blocker.
- Keep media-only vs mixed-failure finisher behavior unchanged.
- Make the normalization visible enough for audits and operator review.

## Non-Goals

- Introducing LLM repair into semantic authority.
- Mining arbitrary prose phrases into canonical destination authority.
- Downgrading true semantic ambiguity into warning-only noise.
- Redesigning builder UI flows beyond existing reporting/finisher contracts.

## Decisions

### Decision: Short-form normalization SHALL only use already-resolved authored aliases
The normalization step SHALL not invent new canonical authority from prose. It SHALL only examine unresolved destination phrases against already-resolved destination aliases already present in the same module payload.

### Decision: Unique anchored collapse SHALL be required
An unresolved short-form phrase SHALL collapse only when exactly one resolved authored alias provides a deterministic anchor. If two or more resolved aliases are equally plausible, the phrase SHALL remain unresolved and blocking.

### Decision: Normalization provenance SHALL remain reviewable
When collapse occurs, the semantic payload and downstream reporting SHOULD preserve the anchor alias and canonical target so the transition from unresolved short form to resolved authority is inspectable.

### Decision: Finisher semantics SHALL not change for true mixed failures
This slice SHALL not weaken the existing mixed-failure contract. Media handoff semantics should appear only because false semantic blockers were removed, not because mixed-failure handling was relaxed.

## Architecture

1. Add a deterministic post-resolution normalization pass inside semantic-authority enrichment or a closely related helper.
2. For each unresolved player-facing destination phrase:
   - compare it against already-resolved authored alias phrases from the same module
   - allow collapse only when one resolved alias is a deterministic strong-form superset or otherwise approved short-form anchor for the unresolved phrase
   - preserve unresolved state when multiple resolved aliases compete
3. Emit normalized provenance fields so publishability and toolkit reporting can show that the phrase was resolved through short-form normalization rather than direct authored resolution.
4. Ensure publishability classification ignores these normalized phrases as blockers while still surfacing genuine unresolved ambiguity.
5. Preserve finisher behavior so media handoff appears only when semantic blockers are actually gone.

## Risks / Trade-offs

- A suffix/substring heuristic that is too broad could collapse phrases incorrectly.
- A heuristic that is too narrow may miss valid short forms like `oath chamber`.
- Additional reporting detail improves traceability but slightly increases payload size.

## Migration Plan

1. Define the deterministic normalization boundary in spec deltas.
2. Implement short-form collapse against existing resolved alias records.
3. Thread normalized provenance through publishability/reporting surfaces.
4. Add focused regression coverage for deterministic success and ambiguous failure.
5. Validate the canary module so only media handoff debt remains when semantic short forms are normalized.

## Verification Plan

- Run targeted semantic-authority and publishability regression tests.
- Prove `Murder_at_the_Drowning_Lass` no longer fails on `oath chamber` and `remnant sanctuary` once deterministic normalization is applied.
- Prove an ambiguous counterexample still remains failed.
- Verify finisher semantics remain failed for real mixed media + semantic cases and become media-handoff eligible only when semantic blockers are truly cleared.

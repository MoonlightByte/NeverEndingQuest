## Why

`plans/module-publication.md` now has Phase 1 and Phase 2 implemented: semantic authority enrichment exists and semantic publication blockers exist. The remaining proof layer before a repo-wide `publishable` gate is a deterministic live-play probe harness that exercises authored travel, escort/handoff, and hidden-NPC discovery semantics the same way a player would encounter them.

## What Changes

- Add a standalone publication-time probe harness that executes deterministic semantic gameplay probes against authored module semantics.
- Define probe fixtures for travel destination resolution, escort or handoff continuity, and hidden/revealable NPC discovery.
- Assert canonical expected targets and explicit failure classes using the semantic-authority substrate and semantic publication blocker policy already in place.
- Keep the probe harness source-driven and deterministic, separate from runtime heuristics and separate from the final repo-wide `publishable` gate.

## Non-Goals

- No repo-wide `publishable` gate or `ready` vs `publishable` split yet.
- No runtime travel, NPC movement, or combat behavior changes.
- No broad rewrite of `audit_module_readiness.py` beyond optional preparation for later integration.
- No probe dependence on live LLM calls or runtime narration loops.

## Capabilities

### New Capabilities
- `module-semantic-publication-probes`: publication-time semantic probe execution SHALL validate authored travel, escort, and hidden-NPC semantics deterministically.
- `module-semantic-probe-fixtures`: probe fixtures SHALL be source-driven, canonical, and stable enough for later CI/release-gate integration.

### Modified Capabilities
- None.

## Impact

- Affected publication tooling: new standalone semantic probe harness under `scripts/`
- Affected semantic-authority tooling: MAY read from `utils/module_semantic_authority.py` and `scripts/module_semantic_authority_audit.py`
- Affected reporting surfaces: additive only; this phase should emit probe pass/fail output without yet becoming the final `publishable` gate
- Compatibility: MUST remain deterministic, additive, and independent of runtime AI behavior

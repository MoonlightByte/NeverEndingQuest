## Why

`module-publication-semantic-authority-foundation` now provides a shared semantic-authority payload and a standalone audit surface, but the findings are still mostly informational. The publication plan's next phase is to turn that substrate into explicit semantic publication blocker classes so unresolved destination phrases, missing NPC authority, and phrase-collision drift are caught before release.

## What Changes

- Upgrade the semantic-authority audit from substrate inspection into publication-oriented blocker classification.
- Promote unresolved named destinations, ambiguous destination phrases, missing NPC scene authority, and dangerous phrase collisions into deterministic blocking findings.
- Keep the semantic publication audit as a standalone CLI/report surface for this phase, without yet wiring it into the repo-wide `publishable` gate.
- Ensure ingest/toolkit report surfaces can reference the stronger audit output without claiming final release gating is complete.

## Non-Goals

- No synthetic gameplay probe harness yet.
- No repo-wide `publishable` gate or `ready` vs `publishable` split yet.
- No runtime travel, NPC movement, or combat behavior changes.
- No broad rewrite of `audit_module_readiness.py` beyond optional preparation for later integration.

## Capabilities

### New Capabilities
- `module-semantic-publication-blockers`: publication-semantic contradictions SHALL be classified into deterministic blocking findings.

### Modified Capabilities
- `module-semantic-authority-audit`: the standalone semantic-authority audit SHALL support publication-oriented fail/degraded outcomes suitable for later CI and release-gate integration.

## Impact

- Affected audit path: `scripts/module_semantic_authority_audit.py`
- Affected shared publication semantics: `utils/module_semantic_authority.py` only if blocker classification reveals missing substrate fields
- Affected reporting surfaces: ingest/toolkit result notes or helper output only as needed to expose stronger audit classes
- Compatibility: MUST remain additive and MUST NOT imply that the final `publishable` gate is implemented in this change

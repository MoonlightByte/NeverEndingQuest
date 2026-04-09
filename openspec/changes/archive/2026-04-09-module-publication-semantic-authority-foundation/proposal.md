## Why

`plans/module-publication.md` now has its spatial and finishing prerequisites in place, but publication work still has a missing semantic substrate: the repository does not emit one deterministic authority layer for named destinations and visible or revealable NPCs. That keeps runtime patches carrying publication debt and prevents later publication audits from consuming one canonical artifact.

## What Changes

- Add a shared semantic-authority enrichment surface that derives deterministic module publication metadata from authored module files.
- Emit a canonical location alias map and a destination phrase map with source provenance and ambiguity signaling.
- Emit an NPC scene-authority map that covers visible NPCs plus hidden or revealable NPC bindings when the authored module makes them discoverable.
- Persist the semantic-authority payload through shared ingest and toolkit-finishing paths so both flows converge on the same contract.
- Add a dedicated semantic-authority audit/report path for uniqueness, traceability, and weak-prose fail-open diagnostics.

## Non-Goals

- No repo-level `publishable` gate.
- No synthetic gameplay probe harness yet.
- No full semantic publication blocker wiring into `audit_module_readiness.py` yet.
- No runtime travel-validator redesign.

## Capabilities

### New Capabilities
- `module-semantic-authority-enrichment`: ingest and toolkit finishing SHALL emit one deterministic semantic-authority payload for publication-oriented destination and NPC semantics.
- `module-semantic-authority-audit`: a dedicated audit/report surface SHALL validate uniqueness, traceability, and ambiguity classes for the semantic-authority payload.

### Modified Capabilities
- None.

## Impact

- Affected shared publication logic: new semantic-authority helper/service under `utils/` or a closely related shared layer
- Affected ingest path: `scripts/homebrew_ingest_dev.py` and/or importer-adjacent publication helpers
- Affected toolkit finishing path: `web/extensions/toolkit_module_finisher.py`
- Affected audit/reporting path: new CLI audit/report script and tests
- Compatibility: MUST remain additive, keep runtime fail-open for already-shipped modules, and avoid implying that full publication safety is complete in this change

## Why

GUI-built homebrew modules are currently failing for a mix of real execution bugs and false publication blockers, which makes the Module Builder feel unreliable even when authored content is structurally close to valid. This needs to be fixed now because illusion-heavy modules like `The_Hidden_City_of_Numillian` expose that the current finisher, readiness contract, and semantic audit layers are over-coupled and are misclassifying narrative prose as canonical world state.

## What Changes

- Replace toolkit finisher monster materialization subprocess execution with the shared in-process materialization path so toolkit builds no longer fail on repo import-context issues.
- Extend the readiness and publishability pipeline to recognize toolkit build provenance separately from ingest-watcher sidecar provenance.
- Tighten semantic destination extraction so evocative prose does not become canonical travel authority unless it comes from canonical location identity fields or equally strong travel evidence.
- Correct hidden-NPC publication probes so visibly authored NPCs do not fail reveal-authority checks that should only apply to hidden/reveal-only NPCs.
- Preserve strict gameplay/media blocking for real structured combatants while allowing scene-only illusion content to remain outside combatant/media requirements through existing scene-entity modeling.
- Add real-path regression coverage for finisher, readiness, and semantic audit behavior so these failures do not recur silently.
- Re-run the improved structural pipeline against existing modules after the fixes land.

## Capabilities

### New Capabilities
- `toolkit-build-source-readiness-contract`: Define toolkit-native provenance handling so GUI builds can satisfy readiness and publishability without watcher-sidecar artifacts.

### Modified Capabilities
- `homebrew-ingest-monster-materialization`: monster materialization MUST support stable in-process execution for toolkit and ingest flows, not depend on fragile subprocess import context.
- `toolkit-module-postbuild-finishing`: toolkit finisher MUST use the shared materialization contract and report stage outcomes from direct execution rather than subprocess parsing.
- `module-readiness-continuity-gate`: readiness MUST support source-aware provenance rules so toolkit builds are not forced through ingest-sidecar requirements.
- `module-semantic-authority-enrichment`: semantic authority MUST avoid promoting freeform evocative prose into canonical destination authority without canonical source evidence.
- `module-semantic-publication-probes`: publication probes MUST treat visible NPC authority and hidden/reveal NPC authority as distinct cases.
- `tt-scene-entity-presence-combat-validity`: scene-only illusion content SHOULD remain outside structured combatant requirements unless explicitly authored as combat-valid.

## Impact

- Affected code:
  - `web/extensions/toolkit_module_finisher.py`
  - `scripts/homebrew_ingest_dev.py`
  - `scripts/audit_module_readiness.py`
  - `scripts/audit_module_publishability.py`
  - `utils/module_semantic_authority.py`
  - `scripts/module_semantic_probe_harness.py`
  - toolkit/readiness/materialization regression tests
- Affected systems:
  - GUI Module Builder post-build flow
  - toolkit readiness and publishability reporting
  - semantic publication audit/probe precision
  - existing module revalidation baseline
- Merge-safety impact:
  - MUST prefer extension-file changes and keep host-file edits minimal and marked with `# TABLETOP MODE:` where required.
- SP/MP compatibility impact:
  - No intended gameplay behavior change for single-player or multiplayer runtime; this change is focused on builder/finisher and publication pipeline correctness.
- Fallback strategy:
  - If a toolkit build cannot satisfy toolkit-native provenance, the finisher MUST fail with explicit source-contract diagnostics rather than generic sidecar-missing errors.
  - If semantic certainty is low, deterministic publication logic SHOULD prefer non-blocking exclusion of prose-derived authority over false canonicalization.

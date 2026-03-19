## Why

Live gameplay context is currently being polluted by mismatched derived location summaries, repeated failed module-integration attempts, and reconcilers consuming stale or mislabeled history as if it were canonical truth. This is now causing continuity breaks such as false re-arrivals, NPC memory drift, and incorrect hostile-state reconciliation during active play, so the runtime hot path needs a focused stabilization pass before more feature work piles on top.

## What Changes

- Add provenance validation for derived location summaries and chronicles so only same-module, same-area, same-location derived context can be reused in live narrator or reconciler flows.
- Quarantine automatic module detection/integration from ordinary live-turn processing so failed module safety checks do not repeatedly contaminate active-session context.
- Narrow location reconciler inputs to same-location authoritative evidence and ignore stale or mismatched derived summaries.
- Harden live narrator scene assembly so current scene packets and recent raw turns outrank older derived memory blocks when they conflict.
- Add transcript-based regressions for the Thornwood/Gorvek continuity failure, including no false second arrival at Bandit Stronghold after the party had already parleyed there.
- Non-goal: this change does NOT redesign general memory architecture, does NOT remove narrator flexibility, and does NOT introduce new module-travel features.

## Capabilities

### New Capabilities
- `tt-location-summary-provenance-guard`: Derived location summaries and chronicles SHALL carry and validate explicit provenance before reuse in runtime context assembly.
- `tt-module-integration-runtime-quarantine`: Automatic module detection/integration SHALL be excluded from ordinary live-turn processing and failed integrations SHALL be quarantined from narrator context.
- `tt-location-reconciler-history-hygiene`: Location reconciliation SHALL consume only same-location authoritative evidence and SHALL ignore mismatched derived history blocks.

### Modified Capabilities
- `tt-narrator-scene-context-hygiene`: Live narrator payload hygiene SHALL validate provenance on derived location memory blocks and SHALL prefer current scene truth over stale derived summaries.

## Impact

- Affected code:
  - `main.py`
  - `core/ai/conversation_utils.py`
  - `core/ai/incremental_compression.py`
  - `utils/compression/multi_pc_conversation_compressor.py`
  - `core/generators/module_stitcher.py`
  - location reconciler/runtime history consumers
  - targeted transcript regressions under `scripts/`
- Systems affected:
  - narrator payload assembly
  - derived location-memory generation and reuse
  - monster/location reconciliation
  - module integration lifecycle during play
- Merge safety:
  - MUST prefer isolated helper functions and minimal `# TABLETOP MODE:` hooks in host files.
- SP/MP compatibility:
  - MUST preserve single-player and multi-player gameplay behavior when context provenance is valid.
  - SHOULD omit stale derived blocks rather than widening narration authority.
- Rollout risk:
  - Over-filtering could drop useful context and reduce continuity.
  - Fallback strategy MUST prefer current location packet plus recent raw turns when provenance validation excludes older derived blocks.

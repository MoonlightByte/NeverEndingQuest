## Why

Recent live play exposed narrator location authority drift in The Thornwood Watch module. While the authoritative world state remained in `NC01` (Corrupted Entry Cave), narration surfaced `NC05`-exclusive finale elements (Malarok present at altar, active Voidstone confrontation), then retconned to an illusion when challenged. In the same sequence, narration also claimed authored adjacent travel routes were blocked without deterministic state support.

This breaks module narrative integrity, confuses progression, and weakens trust in authoritative location state.

## What Changes

- MUST enforce a present-scene contract: narration in the current location cannot instantiate location-exclusive content from another location unless authoritative transition state has committed.
- MUST allow foreshadowing of deeper threats while blocking present-tense scene instantiation of exclusive finale content.
- MUST enforce authored-exit grounding: narration cannot claim a connected route is blocked unless the block is supported by deterministic state/actions.
- MUST fail closed with correction guidance when narrator output violates location exclusivity or authored-exit grounding.
- SHOULD start with a narrow module-targeted guard set for Thornwood (`NC01`/`NC05`) and keep extension points for broader module coverage.
- SHOULD preserve existing reconcile-first transition behavior for valid movement when explicit/inferred transitions are available.

**Non-Goals**
- This change does NOT redesign module topology or quest progression data.
- This change does NOT alter combat mechanics routing.
- This change does NOT change diary cadence or Players Diary generation.
- This change does NOT attempt universal semantic world-modeling for all modules in one pass.

## Capabilities

### New Capabilities
- `tt-location-exclusive-scene-authority`: block location-exclusive present-scene leakage unless location state supports it.
- `tt-authored-exit-grounding`: block unsupported route-blocking narration when authored adjacency still allows travel.
- `tt-foreshadow-vs-presence-contract`: allow atmospheric foreshadowing while enforcing location truth for present-scene claims.

### Modified Capabilities
- `tt-narrator-validation-contract`: add location exclusivity and authored-exit grounding checks to narrator validation correction flow.

## Impact

- Affected code (planned):
  - `main.py`
  - `utils/travel_state_sync_guard.py`
  - new lightweight helper under `utils/` for location exclusivity checks
  - `prompts/system_prompt_compressed.txt`
  - `prompts/validation/validation_prompt_compressed.txt`
  - optional uncompressed prompt mirrors
  - focused regression tests under `scripts/`
- Affected systems:
  - narrator validation retries and correction notes
  - transition and location truth coherence
- Risks:
  - overblocking valid dramatic narration if exclusivity patterns are too broad
  - false positives on environmental hazard descriptions unless scoped carefully
- Fallback:
  - fail-closed with concise correction guidance; no silent acceptance of contradiction-class location drift

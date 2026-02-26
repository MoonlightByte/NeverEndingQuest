## Why

TABLETOP MODE currently allows a narrative/state mismatch where the narrator can say an off-location NPC has arrived (for example, "Priest Ansel arrives") without emitting a corresponding state action. The top NPC strip only renders deterministic state from `party_tracker.json` and current location data, so the NPC does not appear in thumbnails even though narration says they are present.

This causes trust breaks during live facilitation: mechanics may update (for example healing applied via `updateCharacterInfo`) while GUI presence remains out of sync.

## What Changes

- Add a deterministic narrator-response guard that enforces NPC arrival state sync.
  - If narration introduces a known NPC who is not currently present, response MUST include either:
    - `moveBackgroundNPC` (NPC arrives to current location), or
    - `updatePartyNPCs` with `operation: "add"` (NPC joins traveling party).
- Wire the guard into `validate_ai_response()` fail-closed retry flow so invalid narration/state combinations are rejected before acceptance.
- Update narrator/validation prompt contracts so builder and runtime share the same rule.
- Harden top-strip location NPC dedupe logic to compare canonical names by equality (not substring containment) to prevent false suppression edge cases.
- Add targeted regression coverage for valid, invalid, and no-op mention scenarios.

## Capabilities

### New Capabilities
- `tt-npc-arrival-action-contract`: narration that introduces non-present known NPCs is accepted only when state actions in the same response make the NPC present.
- `tt-party-data-npc-dedupe-normalization`: top-strip location NPC filtering uses canonical equality and preserves distinct names.

### Modified Capabilities
- Validation pipeline in `main.py` becomes stricter for NPC presence claims.

## Impact

- Affected code (planned):
  - `main.py`
  - `prompts/system_prompt_compressed.txt`
  - `prompts/validation/validation_prompt_compressed.txt`
  - `prompts/validation/validation_prompt.txt`
  - `web/extensions/tabletop_socket_handlers.py`
  - `scripts/test_npc_arrival_state_sync.py` (new)
- Runtime impact:
  - Narration responses that "spawn" off-location NPCs without actions will be retried.
  - No intended behavior change for already-present NPC references.
- Risk:
  - Moderate validation false-positive risk if mention detection is too broad.
  - Mitigation (MUST): restrict detection to known canonical NPC names and explicit non-present set.
- Merge safety:
  - MUST keep host-file edits additive and marked `# TABLETOP MODE:` where applicable.
  - SHOULD isolate detection logic into helper functions for low-conflict merges.
- SP/MP compatibility:
  - MUST preserve single-player behavior and existing action schema.
  - SHOULD improve TT facilitator trust by enforcing narrative/state coherence.

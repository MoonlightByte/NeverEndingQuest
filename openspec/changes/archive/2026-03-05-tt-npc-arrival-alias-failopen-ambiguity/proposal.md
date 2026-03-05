## Why

NPC arrival state sync can hard-fail valid outputs when NPC identity appears in mixed name forms (for example, short name in narration and full name in party/location/action payloads). The validator currently relies on strict lowercase equality, which causes false negatives and repeated validation retries that end in a hard stop.

This creates a live gameplay blocker and desynchronization risk even when the model emits the correct arrival action types.

## What Changes

- Add alias-aware NPC identity resolution in `utils/npc_arrival_validator.py` for mention/presence/action matching.
- Preserve deterministic fail-closed behavior for true unambiguous misses.
- Add fail-open behavior for ambiguous short-name aliases (user-selected policy): do not hard-fail solely due to ambiguous identity mapping.
- Extend regression coverage in `scripts/test_npc_arrival_state_sync.py` and `scripts/test_npc_arrival_party_exemption.py`.

## Capabilities

1. Alias-equivalent matching for NPC arrival sync
   - Short/full name variants SHALL resolve to the same canonical identity when unambiguous.
2. Ambiguous alias fail-open safety
   - Ambiguous short-name mentions SHOULD not trigger hard validation rejection by themselves.
3. Existing guardrails preserved
   - Party member exemption and fail-closed protection for true missing arrival actions MUST remain intact.

## Impact

- Affected files:
  - `utils/npc_arrival_validator.py`
  - `scripts/test_npc_arrival_state_sync.py`
  - `scripts/test_npc_arrival_party_exemption.py`
- Risk: low-medium (validation-path logic only).
- Compatibility:
  - No schema changes.
  - No prompt contract changes required.
  - Upstream-safe additive patch in TABLETOP MODE validation surface.
- Fallback:
  - If alias resolver fails unexpectedly, validator SHOULD degrade conservatively and avoid introducing false hard-fails from ambiguous aliases.

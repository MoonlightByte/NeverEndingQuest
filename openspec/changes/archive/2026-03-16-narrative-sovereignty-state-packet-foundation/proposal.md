## Why

The current narrator runtime rebuilds world truth from several partially overlapping sources: `party_tracker.json`, area files, DM Note assembly, validation payload assembly, and recent conversation context. This fragmentation makes soft world-state bugs harder to reconcile and has contributed to immersive-play failures where narration, validator context, and persisted state disagree even before a mechanical contradiction exists.

For the gametest release lane, we need a narrow foundation that improves truth-surface coherence without attempting the full reconcile-first architecture in one risky pass. The immediate opportunity is to introduce one shared authoritative packet for current location, party, party NPCs, and nearby world context so later travel and NPC reconciliation work can operate from the same runtime truth.

## What Changes

- Add a narrow `AuthoritativeStatePacket` foundation for narrator-runtime truth assembly.
- Use the packet as the shared machine-readable source for current location/module, reachable topology, party roster, and party NPC roster in the touched paths.
- Align DM Note assembly with the same packet so player-facing and validator-facing state surfaces stop drifting.
- Add packet-aware validation handoff for the touched travel/NPC-ready paths without broad rewriting of unrelated validators.
- Preserve the existing JSON/action schema surface and explicit action flow; this slice only reduces truth duplication.

Non-goals:
- No full world-delta reconciler in this slice.
- No broad prompt rewrite in this slice.
- No Titans/EGO runtime integration in this slice.
- No removal of existing explicit action paths in this slice.
- No broad combat/runtime refactor outside the touched state-packet boundaries.

## Capabilities

### New Capabilities
- `tt-authoritative-state-packet-foundation`: runtime SHALL build a canonical packet for current narrator/validator truth in the touched domains.
- `tt-dm-note-state-packet-parity`: DM Note rendering SHALL reflect the authoritative packet rather than an independent truth assembly path.

### Modified Capabilities
- `tt-narrator-validation-contract`: validation-state handoff SHALL consume authoritative packet truth for packet-enabled domains instead of reconstructing those truths ad hoc.

## Impact

- Primary code:
  - new `utils/authoritative_state_packet.py`
  - `main.py`
  - `utils/multi_pc_dm_note.py`
- Validation touchpoints:
  - narrator validation assembly in `main.py`
  - existing packet-enabled travel/NPC validation handoff paths only
- Tests:
  - new targeted packet/parity regression coverage in `scripts/`
  - small extensions to existing narrator/validation tests if needed

Risks and fallback:
- MUST keep the packet narrow so this remains a gametest stabilization change, not a full runtime rewrite.
- MUST preserve existing explicit action semantics and non-touched gameplay flows.
- SHOULD fail open for optional packet fields when enough current truth exists to preserve compatibility.
- If packet wiring introduces regressions, the fallback is to keep the additive packet helper and revert consumer wiring while preserving the tests and contract artifacts.

Merge-safety / compatibility:
- Changes SHOULD remain additive and hook-based where possible.
- Single-player and tabletop modes MUST continue to function.
- This change is intentionally stronger than upstream truth coherence, but it is not an upstream schema break or action-contract replacement.

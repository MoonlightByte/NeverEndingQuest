## 1. Contract and regression foundation

- [x] 1.1 Add targeted tests or source-contract coverage for the new authoritative state packet field set and builder entrypoints.
- [x] 1.2 Add parity regression coverage showing touched DM Note consumers and touched validation assembly read overlapping location/party/party-NPC truths from the same packet surface.
- [x] 1.3 Add compatibility coverage confirming explicit action-schema turns still behave normally when packet construction is present.

## 2. Packet foundation implementation

- [x] 2.1 Create `utils/authoritative_state_packet.py` with a narrow builder for module/area/location, party roster, party NPC roster, and reachable topology context.
- [x] 2.2 Wire packet construction into the touched narrator runtime path in `main.py` using additive `# TABLETOP MODE:` hooks.
- [x] 2.3 Update touched DM Note assembly in `utils/multi_pc_dm_note.py` to consume packet truth for overlapping fields.
- [x] 2.4 Update touched narrator validation handoff in `main.py` so packet-enabled overlapping truths come from the authoritative packet.

## 3. Verification

- [x] 3.1 `python3 -m py_compile main.py utils/multi_pc_dm_note.py utils/authoritative_state_packet.py <changed_test_files>`
- [x] 3.2 Run the targeted packet/parity regression tests.
- [x] 3.3 Run the existing narrator/validation tests affected by the touched path.
- [x] 3.4 `openspec validate narrative-sovereignty-state-packet-foundation`

## SHOULD Notes

- SHOULD keep packet v1 intentionally narrow for gametest stabilization.
- SHOULD prefer additive helpers and thin host-file hooks over broad movement of existing logic.
- SHOULD preserve current JSON/action schema semantics and treat the packet as runtime truth infrastructure, not protocol replacement.

## 1. Validator Alias Resolution

- [ ] 1.1 Implement canonical identity resolver helpers in `utils/npc_arrival_validator.py` for exact + unique token-subset matching.
- [ ] 1.2 Apply unified resolver when comparing mentioned NPCs against present NPC identities.
- [ ] 1.3 Apply unified resolver when comparing required arrivals against `moveBackgroundNPC` / `updatePartyNPCs add` action targets.
- [ ] 1.4 Implement fail-open ambiguity policy: ambiguous alias mentions do not trigger hard validation failure by themselves.
- [ ] 1.5 Preserve fail-closed behavior for unambiguous missing arrival actions.

## 2. Regression Coverage

- [ ] 2.1 Update `scripts/test_npc_arrival_state_sync.py` with short/full alias parity tests.
- [ ] 2.2 Add ambiguous alias fail-open regression test in `scripts/test_npc_arrival_state_sync.py`.
- [ ] 2.3 Add/adjust party exemption regression in `scripts/test_npc_arrival_party_exemption.py` to ensure party-member rules still hold under alias matching.
- [ ] 2.4 Keep existing strict failure scenario for unambiguous missing arrival action.

## 3. Verification

- [ ] 3.1 `python3 -m py_compile utils/npc_arrival_validator.py main.py`
- [ ] 3.2 `python3 scripts/test_npc_arrival_state_sync.py`
- [ ] 3.3 `python3 scripts/test_npc_arrival_party_exemption.py`
- [ ] 3.4 `openspec validate tt-npc-arrival-alias-failopen-ambiguity`

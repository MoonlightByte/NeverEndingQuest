## 1. Transition Memory Service Foundation

- [ ] 1.1 Create `core/memory/party_transition_memory.py` with retirement and return write helpers (`record_pc_retirement`, `record_pc_return`) using canonical entity IDs and `role_transition` events.
- [ ] 1.2 Implement retrieval helper (`build_return_memory_pack`) that composes bounded transition + social continuity snippets for narration context.
- [ ] 1.3 Export new service functions in `core/memory/__init__.py` and verify imports resolve cleanly.
- [ ] 1.4 **PHASE 1 GATE**: Report Phase 1 evidence and wait approval

## 2. Retirement Flow Integration

- [ ] 2.1 Extend `web/routes/tabletop_party_routes.py` `remove_party_character` to accept optional `departure_text` and snapshot pre-mutation witness context.
- [ ] 2.2 Add runtime guards in `remove_party_character` to block retirement during active combat and when retiring the final party member.
- [ ] 2.3 Wire retirement route to call transition-memory service, apply party mutation, and enqueue retirement narration with explicit-farewell vs mysterious-departure fallback.
- [ ] 2.4 Append retire lifecycle metadata to character `_tabletop_role_history` via `utils/pc_manager.py` helper path.
- [ ] 2.5 **PHASE 2 GATE**: Report Phase 2 evidence and wait approval

## 3. Return Flow Integration

- [ ] 3.1 Update `web/routes/tabletop_party_routes.py` `add_party_character` to persist return transition memory on successful rejoin.
- [ ] 3.2 Build return narration context from `build_return_memory_pack` and enqueue return narration prompt after rejoin.
- [ ] 3.3 Append return lifecycle metadata to character `_tabletop_role_history` while preserving canonical identity fields.
- [ ] 3.4 **PHASE 3 GATE**: Report Phase 3 evidence and wait approval

## 4. UI and Prompt Assets

- [ ] 4.1 Update `web/static/js/tabletop_mode.js` `retireCharacter` flow to collect optional farewell text and send it in remove-character payload.
- [ ] 4.2 Add `prompts/tabletop/retirement_narration.txt` with narration-only instructions and witness reaction context placeholders.
- [ ] 4.3 Add `prompts/tabletop/return_narration.txt` with continuity-focused return framing and bounded memory snippet placeholders.
- [ ] 4.4 **PHASE 4 GATE**: Report Phase 4 evidence and wait approval

## 5. Resilience, Logging, and Verification

- [ ] 5.1 Add structured degraded-mode logging for retirement/return memory persistence outcomes in `web/routes/tabletop_party_routes.py`.
- [ ] 5.2 Ensure fail-open behavior: if memory persistence fails, party add/remove still completes and fallback narration still queues.
- [ ] 5.3 Add `scripts/test_party_retirement_memory.py` for lifecycle event persistence, no-purge guarantees, and return continuity retrieval coverage.
- [ ] 5.4 Run `python3 -m py_compile web/routes/tabletop_party_routes.py web/static/js/tabletop_mode.js core/memory/party_transition_memory.py` and `python3 scripts/test_memory_regression_coverage.py` plus new lifecycle tests.
- [ ] 5.5 **PHASE 5 GATE**: Final verification report and READY FOR REVIEW

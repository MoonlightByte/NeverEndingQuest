## 1. Validation Guard for NPC Arrival State Sync

- [X] 1.1 Add helper logic for deterministic NPC mention/action pairing in validation path (prefer isolated helper function/module).
- [X] 1.2 Integrate helper check into `validate_ai_response()` so contract failures return fail-closed validation reasons.
- [X] 1.3 Ensure guard only targets non-present known NPC mentions and does not require actions for already-present NPC references.
- [X] 1.4 Ensure action acceptance includes both `moveBackgroundNPC` (arrival to location) and `updatePartyNPCs` add (party join).

## 2. Prompt and Validator Contract Alignment

- [X] 2.1 Update `prompts/system_prompt_compressed.txt` with explicit MUST rule for off-location NPC arrivals requiring state action.
- [X] 2.2 Update `prompts/validation/validation_prompt_compressed.txt` with corresponding validity/violation rules.
- [X] 2.3 Update `prompts/validation/validation_prompt.txt` with matching uncompressed rules and examples.

## 3. Party Strip Dedupe Hardening

- [X] 3.1 Update location NPC dedupe in `web/extensions/tabletop_socket_handlers.py` to canonical equality matching.
- [X] 3.2 Preserve existing behavior for true duplicates while preventing substring-based false suppression.

## 4. Regression Coverage

- [X] 4.1 Add `scripts/test_npc_arrival_state_sync.py` for helper and contract behavior.
- [X] 4.2 Cover valid case: non-present NPC mention + matching action passes.
- [X] 4.3 Cover invalid case: non-present NPC mention without matching action fails.
- [X] 4.4 Cover no-op case: already-present NPC mention requires no additional action.
- [X] 4.5 Cover dedupe case: `Ansel` and `Anselara` remain distinct under equality matching.

## 5. Verification

- [X] 5.1 Run `python3 -m py_compile main.py web/extensions/tabletop_socket_handlers.py`.
- [X] 5.2 Run `python3 -m py_compile scripts/test_npc_arrival_state_sync.py`.
- [X] 5.3 Run `python3 scripts/test_npc_arrival_state_sync.py` and confirm pass.
- [X] 5.4 Run `openspec validate tt-npc-arrival-state-sync`.

Guidance (SHOULD, non-blocking):

- Keep helper code side-effect free (read-only analysis of response payload).
- Keep rejection messages concise and actionable for retry correction.

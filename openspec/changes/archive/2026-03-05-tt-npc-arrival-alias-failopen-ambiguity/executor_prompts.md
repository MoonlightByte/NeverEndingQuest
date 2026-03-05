# Executor Prompts - tt-npc-arrival-alias-failopen-ambiguity

This file provides builder-ready prompts for implementing the NPC arrival alias sync fix with user-selected ambiguity policy.

---

## Execution Contract

- MUST preserve existing fail-closed behavior for unambiguous missing arrival actions.
- MUST implement fail-open behavior for ambiguous alias mentions.
- MUST keep edits additive and scoped to validator/tests.
- MUST preserve party-member exemption logic.
- MUST keep Python output/messages ASCII-only.
- SHOULD prefer small anchored edits in `utils/npc_arrival_validator.py` and avoid broad rewrites.
- SHOULD run compile/tests after each prompt.

---

## Prompt 1 - Add Alias Resolver (Tasks 1.1)

Implement canonical identity resolution helpers inside `utils/npc_arrival_validator.py`.

Requirements:
- Add helper(s) that normalize names consistently (case-insensitive, punctuation/spacing tolerant).
- Matching order MUST be:
  1) exact normalized equality,
  2) unique token-subset/word-based match,
  3) otherwise ambiguous/no-match.
- Return enough state to distinguish `matched`, `ambiguous`, and `unmatched` outcomes.

Verification:
- `python3 -m py_compile utils/npc_arrival_validator.py`

---

## Prompt 2 - Wire Resolver Into Validation (Tasks 1.2-1.5)

Update `validate_npc_arrival_state_sync()` and related helper(s) to use unified identity resolution for mention/presence/action checks.

Requirements:
- Presence check MUST treat unambiguous short/full variants as same identity.
- Arrival action check MUST treat unambiguous short/full variants as same identity.
- Ambiguous mention MUST fail-open (do not include in missing-action hard-fail list by itself).
- Unambiguous missing arrival MUST still fail with existing required-action reason format.
- Party-member exemption MUST remain unchanged.

Verification:
- `python3 -m py_compile utils/npc_arrival_validator.py main.py`

---

## Prompt 3 - Add Regression Tests (Tasks 2.1-2.4)

Extend test coverage in:
- `scripts/test_npc_arrival_state_sync.py`
- `scripts/test_npc_arrival_party_exemption.py`

Required tests:
1. Short narration mention + full arrival action => valid.
2. Short narration mention + full present-state identity => valid/no arrival required.
3. Ambiguous short alias (multiple candidate full names) => fail-open (no hard-fail solely from ambiguity).
4. Unambiguous off-location mention without matching arrival action => still invalid (fail-closed).
5. Party-member exemption remains valid under alias-aware matching.

Verification:
- `python3 scripts/test_npc_arrival_state_sync.py`
- `python3 scripts/test_npc_arrival_party_exemption.py`

---

## Prompt 4 - Final Validation and Report (Tasks 3.1-3.4)

Run final checks and summarize outcomes.

Required verification:
- `python3 -m py_compile utils/npc_arrival_validator.py main.py`
- `python3 scripts/test_npc_arrival_state_sync.py`
- `python3 scripts/test_npc_arrival_party_exemption.py`
- `openspec validate tt-npc-arrival-alias-failopen-ambiguity`

Final report MUST include:
- Files changed
- Behavior changes (unambiguous alias pass + ambiguous fail-open)
- Test results
- Any remaining risks

---

## Stop Conditions

- Stop if compile fails and fix before proceeding.
- Stop if tests indicate party-member exemption regression.
- Stop if edits expand beyond validator/test scope.

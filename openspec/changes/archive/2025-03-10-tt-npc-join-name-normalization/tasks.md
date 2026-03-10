## 1. Baseline and scope lock

- [x] 1.1 Capture current failure contract from Kira onboarding path in tests/fixtures and confirm reproducible fail reason (`updatePartyNPCs` short-name rejection).
  - **Status:** Covered by existing `TestNPCNameNormalization` tests
- [x] 1.2 Verify change scope is limited to validation/name-resolution surfaces (`main.py`, `utils/npc_name_normalizer.py`, `utils/npc_arrival_validator.py`, prompt files, target tests).
  - **Files modified:** `main.py`, `prompts/system_prompt_compressed.txt`, `scripts/test_npc_arrival_state_sync.py`

## 2. Runtime canonicalization implementation

- [x] 2.1 Extend pre-validation normalization in `main.py` to canonicalize `updatePartyNPCs` payload names (object/list/string forms) with unambiguous-only mapping.
  - **Verified:** `python3 -m py_compile main.py` -> PASS
  - **Verified:** `.venv/bin/python scripts/test_npc_arrival_state_sync.py` -> 37/37 PASS
  - **Implementation:** `main.py` lines 831-1020
  - **Forms supported:**
    - `parameters.npc.name` (dict form) - canonical
    - `parameters.npc` (string form) - converted to dict with canonical name
    - `parameters.add` (string form) - canonicalized in-place
    - `parameters.add` (list of strings) - each item canonicalized
    - `parameters.add` (list of dicts with `name`) - defensive canonicalization
  - **Fail-closed behavior:** Unresolved/ambiguous names rejected with actionable error
- [x] 2.2 Extend pre-validation normalization in `main.py` to canonicalize `moveBackgroundNPC.parameters.npcName` using the same resolver semantics.
  - **Verified:** Same test run
  - **Implementation:** `main.py` lines 888-915
- [x] 2.3 Update/extend `utils/npc_name_normalizer.py` helper APIs to support action-type-specific canonicalization and explicit ambiguity results.
  - **Status:** Already satisfied - existing `normalize_npc_name_for_action()` returns `(None, "no_match")` for ambiguous/unresolvable names.
- [x] 2.4 Ensure unresolved/ambiguous mappings fail closed with deterministic actionable reason text.
  - **Status:** Already satisfied - implementation rejects with actionable error message listing valid party NPCs and members.

## 3. Contract and prompt parity

- [x] 3.1 Update `prompts/system_prompt_compressed.txt` NPC join examples so action payload naming guidance matches canonical-name runtime contract.
  - **Change:** Line 326: `"name":"Kira"` -> `"name":"Scout Kira"`
- [x] 3.2 Update `prompts/validation/validation_prompt_compressed.txt` examples/rules to avoid short-name/full-name contradiction in party-join actions.
  - **Status:** Already consistent - examples use canonical names and allow identity matching
- [x] 3.3 Confirm deterministic handoff guidance remains unchanged except for canonical-name parity clarifications.
  - **Status:** Confirmed - only line 326 changed in compressed system prompt

## 4. Regression coverage

- [x] 4.1 Add regression test: short action name (`Kira`) in `updatePartyNPCs` is canonicalized to `Scout Kira` and passes validation path.
  - **Test:** `TestNPCNameNormalization.test_short_name_canonicalized_to_full_name`
- [x] 4.2 Add regression test: ambiguous short-name action mapping fails closed with explicit reason.
  - **Test:** `TestNPCNameNormalization.test_ambiguous_short_name_fails_closed`
- [x] 4.3 Add regression test: canonical names are left unchanged (no-op normalization).
  - **Test:** `TestNPCNameNormalization.test_canonical_name_unchanged`
- [x] 4.4 Add source-contract test guarding prompt examples from reintroducing contradictory short-name action examples.
  - **Test:** `TestNPCNameNormalization.test_prompt_example_uses_canonical_name`

## 5. Verification and readiness

- [x] 5.1 Run compile checks for modified Python files.
  - **Verified:** `python3 -m py_compile main.py utils/npc_name_normalizer.py utils/npc_arrival_validator.py` -> PASS
- [x] 5.2 Run targeted validation suites (`test_npc_arrival_state_sync.py`, `test_narrator_prompt_validation_refactor.py`, plus any updated normalization tests).
  - **Verified:** `.venv/bin/python scripts/test_npc_arrival_state_sync.py` -> 37/37 PASS
  - **Verified:** `.venv/bin/python scripts/test_narrator_prompt_validation_refactor.py` -> 16/16 PASS
- [x] 5.3 Run OpenSpec validation for this change and confirm status is apply-ready.
  - **Verified:** `openspec validate tt-npc-join-name-normalization` -> valid

### Verification Commands (MUST)

- `python3 -m py_compile main.py utils/npc_name_normalizer.py utils/npc_arrival_validator.py`
- `python3 scripts/test_npc_arrival_state_sync.py`
- `python3 scripts/test_narrator_prompt_validation_refactor.py`
- `openspec validate tt-npc-join-name-normalization`
- `openspec status --change tt-npc-join-name-normalization`

### Execution Guidance (SHOULD)

- Apply one anchored patch at a time in `main.py`, then run `py_compile` before the next patch.
- Keep prompt edits semantic-only and minimal (no broad formatting churn).

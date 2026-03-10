## 1. Parity Safety Net

- [x] 1.1 Add targeted regression coverage for phase-1 action-contract parity, explicitly scoped to the covered `rest` action.
- [x] 1.2 Add regression coverage that checks `rest` support presence in both compressed and uncompressed prompt/validator files plus runtime references.
- [x] 1.3 Add regression coverage that fails on stale validator wording requiring direct `updateCharacterInfo` rest recovery for covered rest flows.

## 2. Prompt Contract Alignment

- [x] 2.1 Update `prompts/system_prompt_compressed.txt` and `prompts/validation/validation_prompt_compressed.txt` so `rest` is documented as a first-class supported action with aligned bundle expectations.
- [x] 2.2 Update `prompts/system_prompt.txt` and `prompts/validation/validation_prompt.txt` to mirror the same `rest` contract and remove contradictory legacy guidance in the covered slice.

## 3. Runtime Contract Audit

- [x] 3.1 Audit `core/ai/action_handler.py` and adjacent validation wiring for the covered phase-1 action slice, confirming prompt-documented `rest` behavior matches runtime semantics without broad mechanics rewrites.
- [x] 3.2 Add minimal compatibility handling or targeted comments only if required to keep covered auxiliary action contracts stable while parity changes land. (No runtime shim required.)
- [x] 3.3 Record any newly confirmed save/restore/list/delete-save or `createNewModule` drift as deferred follow-up work rather than expanding this change mid-build. (Deferred and implemented in follow-up change.)

## 4. Verification

- [x] 4.1 Run targeted test coverage for parity and rest contract alignment, fixing failures until green.
- [x] 4.2 Run focused syntax and OpenSpec validation checks for the touched files and the change scaffold.

## 1. Parity Safety Net

- [x] 1.1 Add targeted regression coverage for the covered save-management actions and `createNewModule` across runtime and both prompt variants.
- [x] 1.2 Add regression coverage that fails if validator guidance still requires `saveName` for `restoreGame` or `deleteSave`.
- [x] 1.3 Add regression coverage that fails if `createNewModule` validation still treats rigid `moduleName` plus `startingLocation` as the only valid contract.

## 2. Prompt Contract Alignment

- [x] 2.1 Update `prompts/system_prompt_compressed.txt` and `prompts/validation/validation_prompt_compressed.txt` so covered save-management actions reflect runtime parameter shapes.
- [x] 2.2 Update the same compressed files so `createNewModule` is documented as a narrative-driven handoff with `narrative` as the canonical minimum payload.
- [x] 2.3 Update `prompts/system_prompt.txt` and `prompts/validation/validation_prompt.txt` to mirror the same covered contracts and remove contradictory legacy guidance in this slice.

## 3. Runtime Contract Audit

- [x] 3.1 Audit `core/ai/action_handler.py` and `core/generators/module_builder.py` for the covered actions, confirming prompt-documented behavior matches runtime semantics without broad rewrites.
- [x] 3.2 Add the smallest compatibility shim or targeted normalization only if tests reveal a live legacy dependency for the covered actions. (No shim required.)
- [x] 3.3 Record any newly confirmed drift outside the covered action set as deferred follow-up work rather than expanding this change mid-build. (No additional out-of-scope drift discovered in this pass.)

## 4. Verification

- [x] 4.1 Run targeted parity and contract-alignment tests, fixing failures until green.
- [x] 4.2 Run focused syntax and OpenSpec validation checks for the touched files and the change scaffold.

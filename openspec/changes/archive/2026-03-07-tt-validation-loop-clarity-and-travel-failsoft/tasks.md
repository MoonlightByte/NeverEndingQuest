## 1. Prompt and Input Simplification

- [x] 1.1 Stop appending legacy common instruction tail on multi-PC path in `main.py`.
- [x] 1.2 Keep existing structured multi-PC DM note content unchanged except duplication removal.
- [x] 1.3 Ensure transition pre-validation receives raw player utterance (not DM-note-augmented string).

## 2. NPC Arrival Guard Fail-Soft for Travel Turns

- [x] 2.1 Extend NPC arrival validator interface to accept travel-intent context.
- [x] 2.2 Add explicit-arrival semantic detection helper (arrive/join/enter/appear-from-elsewhere).
- [x] 2.3 Apply fail-soft branch only for travel-intent turns without explicit-arrival semantics.
- [x] 2.4 Preserve fail-closed behavior for explicit arrivals and keep existing exemptions/alias handling.

## 3. Retry Loop De-Priming

- [x] 3.1 For deterministic guard failures, do not append failed assistant output back into history.
- [x] 3.2 Replace verbose retry note with concise normalized correction note.
- [x] 3.3 Add repeated-reason short-circuit (same deterministic reason twice -> early stop message).

## 4. Prompt Contract Slimdown

- [x] 4.1 Tighten `@NPC_ARRIVAL_STATE_SYNC` wording in `prompts/system_prompt_compressed.txt` to explicit-arrival semantics.
- [x] 4.2 Mirror the same narrowed contract in `prompts/validation/validation_prompt_compressed.txt`.
- [x] 4.3 Keep MUST/SHOULD style and avoid adding new broad constraints.

## 5. Tests and Verification

- [x] 5.1 Extend `scripts/test_npc_arrival_state_sync.py` with travel-intent fail-soft and explicit-arrival fail-closed cases.
- [x] 5.2 Add targeted retry-loop regression test for deterministic failure handling.
- [x] 5.3 Run compile checks for modified Python files.
- [x] 5.4 Run affected test suites and confirm all pass.
- [x] 5.5 Run `openspec validate tt-validation-loop-clarity-and-travel-failsoft`.

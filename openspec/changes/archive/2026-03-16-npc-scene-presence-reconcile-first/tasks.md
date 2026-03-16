## 1. Contract and transcript coverage first

- [x] 1.1 Add transcript-driven regression coverage for the Maelo-style scene-presence loop that SHOULD reconcile instead of hard-fail.
- [x] 1.2 Add regression coverage confirming foreshadowing/informational NPC mentions remain action-free.
- [x] 1.3 Add regression coverage confirming explicit party-join narration still requires `updatePartyNPCs`.
- [x] 1.4 Add regression coverage confirming ambiguous NPC identity does not silently auto-commit scene presence.

## 2. OpenSpec contract scaffolding

- [x] 2.1 Add proposal/design/tasks artifacts for `npc-scene-presence-reconcile-first`.
- [x] 2.2 Add new capability delta for reconcile-first NPC scene presence.
- [x] 2.3 Add narrator-validation delta clarifying deterministic scene-presence reconciliation authority.
- [x] 2.4 Add name-resolution delta preserving ambiguity safety under scene-presence reconciliation.

## 3. Runtime implementation (after review)

- [x] 3.1 Update `utils/npc_arrival_validator.py` to classify scene presence separately from party membership.
- [x] 3.2 Update `main.py` so safe scene presence can reconcile instead of immediately returning deterministic failure.
- [x] 3.3 Preserve explicit action precedence and explicit party-join requirements.
- [x] 3.4 Keep ambiguity and non-scene-safe cases fail-safe.

## 4. Verification

- [x] 4.1 `python3 -m py_compile main.py utils/npc_arrival_validator.py core/ai/action_handler.py <changed_test_files>`
- [x] 4.2 Run the new G3 transcript-driven tests.
- [x] 4.3 Run existing NPC arrival / retry-loop regressions affected by the touched path.
- [x] 4.4 `openspec validate npc-scene-presence-reconcile-first`

## SHOULD Notes

- SHOULD keep G3 narrower than travel reconciliation.
- SHOULD treat scene presence and party membership as separate outcomes.
- SHOULD prefer additive reconcile-first hooks over broad validator rewrites.

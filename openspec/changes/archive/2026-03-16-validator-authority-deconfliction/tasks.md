## 1. Contract and transcript coverage first

- [x] 1.1 Add transcript-driven regression coverage for travel-reconciled turn where LLM still complains about missing travel state action.
- [x] 1.2 Add transcript-driven regression coverage for NPC scene-presence reconciled turn where LLM still complains about missing NPC movement action.
- [x] 1.3 Add transcript-driven regression coverage for mixed-domain failure: reconciled travel/NPC domain is valid but unrelated invalid action remains blocking.
- [x] 1.4 Add regression coverage confirming deterministic authoritative fail still blocks and is not overridden.
- [x] 1.5 Add telemetry/routing regression coverage for suppressed domains and remaining failure domains.

## 2. Deterministic handoff payload foundation

- [x] 2.1 Replace flat narrator deterministic payload in `main.py` with domain-scoped payload assembly.
- [x] 2.2 Keep payload v1 limited to `travel_state_sync`, `npc_state_sync`, and `mechanics_precheck`.
- [x] 2.3 Emit structured summary metadata for reconciled domains and authoritative failures.

## 3. Validation authority deconfliction runtime

- [x] 3.1 Replace arrival-only override logic in `main.py` with generic domain-based deconfliction.
- [x] 3.2 Preserve blocking behavior for mixed-domain and unreconciled failures.
- [x] 3.3 Update `utils/validation_routing.py` with deterministic routing reason codes for authoritative-domain suppression and mixed review.
- [x] 3.4 Keep host-file edits additive and marked with `# TABLETOP MODE:` comments.

## 4. Prompt and retry alignment

- [x] 4.1 Update compressed validation prompt with authoritative-domain handoff rules.
- [x] 4.2 Update uncompressed validation prompt with authoritative-domain handoff examples.
- [x] 4.3 Narrow retry correction generation so reconciled-domain-only failures do not produce retry instructions.

## 5. Verification

- [x] 5.1 `python3 -m py_compile main.py utils/validation_routing.py <changed_test_files>`
- [x] 5.2 Run the new G4 transcript-driven tests.
- [x] 5.3 Run existing narrator validation, retry hygiene, and routing telemetry regressions affected by the touched path.
- [x] 5.4 `openspec validate validator-authority-deconfliction`

## 6. Closeout Focus (Prompt / Retry Alignment)

- [x] 6.1 Replace flat arrival-only deterministic handoff wording in `prompts/validation/validation_prompt_compressed.txt` with domain-scoped authority guidance.
- [x] 6.2 Replace flat arrival-only deterministic handoff wording in `prompts/validation/validation_prompt.txt` with domain-scoped authority guidance and mixed-domain examples.
- [x] 6.3 Add source-contract or prompt tests that lock `travel_state_sync`, `npc_state_sync`, and `mechanics_precheck` prompt authority language.
- [x] 6.4 Narrow retry correction generation in `main.py` so reconciled-domain-only complaints do not create retry instructions.
- [x] 6.5 Add retry-specific regressions proving mixed-domain failures still generate correction only for unreconciled domains.

## SHOULD Notes

- SHOULD keep G4 narrator-only and avoid combat validation scope creep.
- SHOULD prefer structured domain payloads over keyword-based override logic.
- SHOULD keep payload v1 intentionally small so future changes can extend it safely.

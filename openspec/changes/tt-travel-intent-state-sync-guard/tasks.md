# Tasks: tt-travel-intent-state-sync-guard

## 1. Contract Tests First

- [x] 1.1 Add targeted regression tests for clear travel-intent narration that reaches a new location with `actions: []` or no `transitionLocation`.
- [x] 1.2 Add regression tests for valid blocker and clarification responses that keep the party at the current location without `transitionLocation`.
- [x] 1.3 Add regression tests for contradictory dual-location travel narration in a single response.
- [x] 1.4 Add regression tests for ambiguous travel prose that should fail open.

## 2. Runtime Guard Implementation

- [x] 2.1 Implement a narrow deterministic travel-state sync guard in the narrator response validation path for travel-intent turns.
- [x] 2.2 Reuse existing travel-intent classification and retry-local correction flow instead of creating parallel state.
- [x] 2.3 Ensure the guard does not disturb existing same-location stripping, transition pre-validation, or updateTime fallback behavior.

## 3. Prompt / Validator Parity (Only If Needed)

- [ ] 3.1 Update compressed and uncompressed validation guidance only if runtime tests show contract drift or repeated correction mismatch.

## 4. Verification

- [x] 4.1 `python3 -m py_compile main.py <changed_test_files>`
- [x] 4.2 Run targeted travel-state sync regression tests.
- [x] 4.3 Run existing travel/validation regression tests affected by the touched path.
- [x] 4.4 `openspec validate tt-travel-intent-state-sync-guard`

## SHOULD Notes

- SHOULD keep the guard deterministic and based on explicit travel intent plus explicit arrival/state cues.
- SHOULD avoid destination inference from vague narration when no safe conclusion can be drawn.
- SHOULD keep corrections concise so retries do not become self-priming travel loops.

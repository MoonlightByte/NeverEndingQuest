## 1. Contract and transcript coverage

- [x] 1.1 Add transcript-driven regression tests for explicit narrated arrival without explicit `transitionLocation` that should now auto-commit legally.
- [x] 1.2 Add regression tests for legal travel-progress narration that should persist in-transit/progress state without forcing exact arrival.
- [x] 1.3 Add regression tests for ambiguous travel narration that must not auto-commit wrong canon.
- [x] 1.4 Add regression tests for impossible or same-location travel that must remain blocked.

## 2. Reconcile-first travel implementation

- [x] 2.1 Implement or wire authoritative-packet travel inputs needed for reconcile-first travel decisions.
- [x] 2.2 Update `utils/travel_state_sync_guard.py` and/or adjacent travel logic so legal travel can reconcile instead of hard-failing solely for missing explicit travel action.
- [x] 2.3 Add runtime handling for in-transit/progress state when travel is clear but exact arrival is not yet justified.
- [x] 2.4 Preserve explicit `transitionLocation` precedence and same-location/impossible-topology safety checks.
- [x] 2.5 Extend deterministic travel-time sync so inferred travel commits receive synchronized time advancement.

## 3. Validation narrowing and parity

- [x] 3.1 Narrow travel-domain validation in `main.py` so legal/resolvable travel prefers reconciliation over reject-first retry behavior.
- [x] 3.2 Update prompt/validation wording only if runtime regressions show contract mismatch after implementation.

## 4. Verification

- [x] 4.1 `python3 -m py_compile main.py utils/travel_state_sync_guard.py core/managers/location_manager.py core/ai/action_handler.py <changed_test_files>`
- [x] 4.2 Run targeted travel reconciliation regression tests.
- [x] 4.3 Run existing travel/validation regression tests affected by the touched path.
- [x] 4.4 `openspec validate travel-reconcile-first-autocommit`

## SHOULD Notes

- SHOULD keep this slice travel-only and defer NPC presence reconciliation unless travel work proves it is immediately required.
- SHOULD preserve the current JSON/action schema as a preferred explicit path while reducing dependence on perfect action emission.
- SHOULD prefer additive reconcile-first hooks over broad deletion of old travel paths in one pass.

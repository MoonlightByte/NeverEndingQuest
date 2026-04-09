## 1. Location exclusivity guard foundation

- [x] 1.1 Add a deterministic helper that evaluates narrator output for location-exclusive present-scene leakage against authoritative `currentLocationId`.
- [x] 1.2 Implement Thornwood-first exclusivity anchors for `NC05` finale content (Malarok present, ritual altar, central Voidstone confrontation).
- [x] 1.3 Ensure the helper distinguishes foreshadowing language from present-scene instantiation.

## 2. Runtime narrator validation integration

- [x] 2.1 Wire exclusivity evaluation into narrator validation flow in `main.py` fail-closed path.
- [x] 2.2 Surface concise correction guidance when exclusivity violations occur.
- [x] 2.3 Preserve existing reconcile-first transition behavior for valid travel actions.

## 3. Authored-exit grounding guard

- [x] 3.1 Add a deterministic check for unsupported route-blocking narration when authored adjacency still allows travel.
- [x] 3.2 Accept route-block claims only when backed by deterministic state/actions or authored blocker metadata.
- [x] 3.3 Reject unsupported blockage claims with correction guidance.

## 4. Prompt and validator contract alignment

- [x] 4.1 Update narrator prompt contract to clarify foreshadowing vs present-scene exclusivity.
- [x] 4.2 Update validator prompt contract with invalid/valid examples for NC01/NC05 exclusivity and route-block grounding.
- [x] 4.3 Keep uncompressed mirrors aligned if compressed prompts are updated.

## 5. Regression and verification

- [x] 5.1 Add targeted tests for NC01 cannot instantiate NC05 finale scene anchors without transition.
- [x] 5.2 Add targeted tests for unsupported blockage claims on authored adjacent exits.
- [x] 5.3 Run focused compile/tests and module validation using `.venv/bin/python` for dependency-sensitive checks.

SHOULD: Keep this change narrow and contradiction-class focused; avoid broad narrative style policing.
SHOULD: Extend beyond Thornwood only after Thornwood guard quality is verified.

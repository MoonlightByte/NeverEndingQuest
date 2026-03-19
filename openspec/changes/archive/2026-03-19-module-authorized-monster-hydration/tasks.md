## 1. Authorization Roster Foundation

- [x] 1.1 Add a helper that derives a normalized monster authorization roster from authored module content and existing module monster files.
- [x] 1.2 Define and document which authored module fields count as authoritative monster sources for runtime authorization.
- [x] 1.3 Add regression coverage proving authored `Cultist` references in `Night_of_the_Restless_Dead` are recognized as authorized while unrelated narration-only names are not.

## 2. Runtime Monster Resolution

- [x] 2.1 Integrate authorization lookup into `core/generators/combat_builder.py` before the current tabletop fail-closed missing-monster branch.
- [x] 2.2 Implement reuse-first resolution for authorized missing standard monsters before builder generation is attempted.
- [x] 2.3 Implement controlled hydration fallback for authorized missing monsters and persist successful results to the active module monster directory.
- [x] 2.4 Preserve fail-closed rejection for unauthorized monsters and ensure hydration is skipped for that class.

## 3. Failure Surfacing and Safety

- [x] 3.1 Update encounter failure reporting to distinguish `authorized_monster_hydration_failed` from unauthorized monster rejection.
- [x] 3.2 Ensure failed encounter generation does not emit misleading combat-start narration in either failure class.
- [x] 3.3 Verify existing successful encounter startup behavior remains unchanged when monster files already exist.

## 4. Verification

- [x] 4.1 Add or update focused regressions for authorized `Cultist` hydration, unauthorized `Cult Fanatic` rejection, and clearly hallucinated monster rejection.
- [x] 4.2 Run `python3 -m py_compile` on all touched Python files.
- [x] 4.3 Run targeted combat regression suites and any new monster-authorization tests.
- [x] 4.4 Run `openspec validate module-authorized-monster-hydration` and confirm the change is apply-ready.

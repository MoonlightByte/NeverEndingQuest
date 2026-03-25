## 1. Contract Locks and Regressions First

- [x] 1.1 Extend `scripts/test_module_authorized_monster_hydration.py` to lock deterministic canonicalization behavior for:
  - exact authorized base match (`Cultist` -> `cultist`)
  - canonicalizable flavor (`Cultist Leader` -> `cultist`)
  - adjective flavor (`Red-Cloaked Cultist` -> `cultist`)
  - exact stronger authorized identity remains exact (`Bandit Captain` stays `bandit_captain` when explicitly authorized)
  - ambiguous label fails closed (`Skeleton Guard` when multiple canonical candidates exist)
  - nonsense label fails closed
- [x] 1.2 Add or extend source-contract coverage so `core/generators/combat_builder.py` is required to persist split identity output (`name` flavored, `monsterType` canonical).
- [x] 1.3 Keep pre-implementation failures narrow and expected: new tests SHOULD fail only on missing canonicalization behavior, not unrelated regressions.

## 2. Resolver Foundation

- [x] 2.1 Add `resolve_authorized_monster_reference(...)` and minimal supporting helpers in `utils/module_monster_authority.py`.
- [x] 2.2 Keep `authorize_module_monster(...)` backward compatible while allowing canonical resolution metadata to be reused by hydration/runtime callers.
- [x] 2.3 Update `materialize_authorized_monster_file(...)` to hydrate/reuse canonical resolved identities while preserving existing fail classes.
- [x] 2.4 Surface deterministic unauthorized reason detail for unresolved vs ambiguous matches without widening the pass boundary.

## 3. Combat Runtime Integration

- [x] 3.1 Update `core/generators/combat_builder.py` to consume structured resolver output rather than assuming raw input label equals canonical monster identity.
- [x] 3.2 Preserve encounter enemy `name` as the flavored display/target label.
- [x] 3.3 Persist canonical resolved monster identity in encounter `monsterType`.
- [x] 3.4 Keep duplicate-name suffixing stable per display label and avoid accidental canonical-type overwrite of target/display identity.
- [x] 3.5 Preserve existing exact-match behavior when monster files already exist locally.

## 4. Prompt Contract Nudge

- [x] 4.1 Update `prompts/system_prompt_compressed.txt` monster-source guidance to prefer canonical statblock names in `createEncounter.monsters`.
- [x] 4.2 Clarify that leader/title/color/rank flavor belongs in `encounterSummary` unless the stronger canonical variant is explicitly authored.

## 5. Verification

- [x] 5.1 Run `python3 -m py_compile utils/module_monster_authority.py core/generators/combat_builder.py scripts/test_module_authorized_monster_hydration.py`
- [x] 5.2 Run `python3 scripts/test_module_authorized_monster_hydration.py`
- [x] 5.3 Run targeted combat regression coverage touching encounter startup or encounter shape if touched by implementation.
- [x] 5.4 Run `openspec validate combat-canonical-monster-reference-resolution`

## SHOULD Notes

- SHOULD keep canonicalization deterministic and explainable; avoid fuzzy-scoring heuristics.
- SHOULD prefer one anchored edit block per Python file at a time, with immediate `py_compile` checks after each touched file.
- SHOULD keep this slice limited to enemy monster reference resolution only.

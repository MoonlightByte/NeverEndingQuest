# Executor Prompts: combat-canonical-monster-reference-resolution

## Execution Contract

MUST:
- Keep scope strictly to enemy monster reference canonicalization for `createEncounter`.
- Preserve fail-closed behavior for unresolved and ambiguous references.
- Preserve authored-content-only authorization; no runtime narration/chat history authorization.
- Preserve error classes `unauthorized_monster_reference` and `authorized_monster_hydration_failed`.
- Preserve split encounter identity semantics:
  - `name` = display/target label
  - `monsterType` = canonical mechanics/template key
- Preserve exact stronger authorized identities when they already exist (for example `Bandit Captain`).
- Keep host-file edits minimal and mark them with `# TABLETOP MODE:` comments.
- Keep Python user-facing output/log text ASCII-only.

SHOULD:
- Prefer helper-first work in `utils/module_monster_authority.py`.
- Keep `combat_builder.py` integration thin and declarative.
- Apply one anchored patch at a time in large Python files, then run `python3 -m py_compile <touched_file>` before the next patch.
- Keep matching deterministic and explainable from slugs/tokens.

## Prompt 1 - Lock Contract Tests First (Tasks 1.1-1.3)

Implement tests before runtime edits.

Allowed files:
- `scripts/test_module_authorized_monster_hydration.py`
- any existing narrow contract test file already covering `combat_builder.py` imports/source contracts

Required coverage:
1. `Cultist` exact authorized base identity remains authorized.
2. `Cultist Leader` resolves to canonical `cultist`.
3. `Red-Cloaked Cultist` resolves to canonical `cultist`.
4. `Bandit Captain` remains exact when explicitly authorized.
5. `Skeleton Guard` fails closed when multiple canonical candidates are plausible.
6. Nonsense label fails closed.
7. `combat_builder.py` contract must preserve split identity output (`name` flavored, `monsterType` canonical).

Guardrails:
- Do not edit runtime code in this step.
- Keep assertions narrowly targeted at canonicalization behavior.

Verification gate:
- `python3 -m py_compile scripts/test_module_authorized_monster_hydration.py`
- `python3 scripts/test_module_authorized_monster_hydration.py`
- Expect newly added canonicalization assertions to fail before implementation; unrelated existing tests must stay green.

## Prompt 2 - Implement Resolver Foundation (Tasks 2.1-2.4)

Implement canonical resolution in helpers only.

Allowed files:
- `utils/module_monster_authority.py`

Required implementation:
- Add `resolve_authorized_monster_reference(...)` and minimal helper(s).
- Keep `authorize_module_monster(...)` backward compatible.
- Route `materialize_authorized_monster_file(...)` through canonical resolution.
- Preserve existing fail classes.
- Add deterministic unauthorized reason detail for unresolved vs ambiguous failures.

Guardrails:
- No module-specific alias hacks.
- No fuzzy-score matcher.
- No authorization widening beyond authored module sources.
- Do not degrade exact stronger authorized variants to weaker base species.

Edit strategy:
- Apply one anchored patch at a time.
- Run `python3 -m py_compile utils/module_monster_authority.py` after each logical patch.

Verification gate:
- `python3 -m py_compile utils/module_monster_authority.py scripts/test_module_authorized_monster_hydration.py`
- `python3 scripts/test_module_authorized_monster_hydration.py`

## Prompt 3 - Integrate Combat Builder Split Identity (Tasks 3.1-3.5)

Integrate structured resolver output into encounter generation.

Allowed files:
- `core/generators/combat_builder.py`
- `scripts/test_module_authorized_monster_hydration.py`
- existing narrow combat contract tests if needed

Required implementation:
- Consume structured resolver/materialization output in `combat_builder.py`.
- Preserve encounter `name` as the original flavored label.
- Persist canonical `monsterType` from resolver output.
- Keep duplicate suffixing keyed by display label.
- Preserve exact local-file success behavior.

Guardrails:
- Do not refactor unrelated encounter-building code.
- Do not change downstream combat manager targeting behavior in this step.

Edit strategy:
- Patch one logical block at a time.
- Run `python3 -m py_compile core/generators/combat_builder.py` after each block.

Verification gate:
- `python3 -m py_compile utils/module_monster_authority.py core/generators/combat_builder.py scripts/test_module_authorized_monster_hydration.py`
- `python3 scripts/test_module_authorized_monster_hydration.py`
- run touched combat regression coverage if encounter shape assertions changed

## Prompt 4 - Prompt Nudge and Final Verification (Tasks 4.1-5.4)

Allowed files:
- `prompts/system_prompt_compressed.txt`
- any touched tests if wording contract tests exist

Required implementation:
- Update monster-source guidance to prefer canonical statblock names in `createEncounter.monsters`.
- Clarify that title/color/rank flavor belongs in `encounterSummary` unless the stronger canonical variant is explicitly authored.

Final verification gate:
- compile touched Python files
- rerun `python3 scripts/test_module_authorized_monster_hydration.py`
- rerun touched combat regression suite(s)
- `openspec validate combat-canonical-monster-reference-resolution`

Report format:
- files changed
- commands run
- PASS/FAIL per verification gate
- exact outcomes for: `Cultist`, `Cultist Leader`, `Red-Cloaked Cultist`, `Bandit Captain`, `Skeleton Guard`, nonsense label
- confirmation that unresolved and ambiguous references still fail closed

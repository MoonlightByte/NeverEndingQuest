## Why

`createEncounter` currently treats each monster label as if it must already be the exact authored canonical monster identity. That protects against hallucinated enemies, but it breaks on common flavored labels such as `Cultist Leader`, `Red-Cloaked Cultist`, or similar author/model wording when the module only authorizes the canonical base statblock (`Cultist`).

This is a scaling problem, not a one-off module bug. As more modules are ingested, wording variance will continue to produce false combat-start failures unless runtime can deterministically separate:
- display flavor used in narration/UI/targeting, from
- canonical statblock identity used for authorization, hydration, and mechanics.

## Objective

Add a deterministic canonical monster-reference resolution layer before encounter authorization so flavored enemy labels can resolve to an authored canonical monster identity when - and only when - resolution is unique and explainable.

## What Changes

- Add a canonical monster-reference resolver in `utils/module_monster_authority.py`.
- Resolve `createEncounter.monsters[]` entries before authorization/hydration.
- Preserve split encounter identity:
  - encounter `name` = flavored display/target label
  - encounter `monsterType` = canonical statblock identity
- Preserve fail-closed behavior for:
  - unresolved labels
  - ambiguous labels
  - narration-only monsters not present in authored module authority sources
- Preserve existing monster hydration flow, but run it against the resolved canonical identity.
- Expand regression coverage to lock exact-match, canonicalizable, stronger-exact, ambiguous, and nonsense cases.
- Tighten prompt guidance so `createEncounter.monsters` prefers canonical statblock names and leaves rank/color/title flavor to `encounterSummary`.

## Non-Goals

- This change MUST NOT authorize monsters from freeform narration or chat history.
- This change MUST NOT add module-specific alias hacks.
- This change MUST NOT auto-upgrade weaker authored monsters into stronger variants.
- This change MUST NOT redesign combat targeting semantics or encounter update routing.
- This change MUST NOT broaden NPC hostility promotion logic; enemy monster reference resolution only.

## Capabilities

### New Capabilities
- `tt-combat-canonical-monster-reference-resolution`: Encounter monster labels SHALL resolve to canonical authored monster identities when deterministic.

### Modified Capabilities
- `tt-module-authorized-monster-hydration`: Authorization and hydration SHALL run against resolved canonical monster identities.
- `tt-createencounter-failure-surfacing`: Unauthorized encounter failures SHALL distinguish unresolved vs ambiguous canonicalization when available.

## Risks

- Overly broad canonicalization could widen hallucination acceptance.
- Overly narrow canonicalization could keep valid encounters failing.
- Name/monsterType divergence could break downstream combat behavior if encounter identity split is not preserved consistently.

## Fallback

- If deterministic canonicalization proves unsafe, rollback SHALL revert resolver integration and return to the current exact-match fail-closed authorization path.
- Existing exact authorized monster behavior MUST remain valid throughout rollout.

## Impact

- Affected code:
  - `utils/module_monster_authority.py`
  - `core/generators/combat_builder.py`
  - `prompts/system_prompt_compressed.txt`
  - `scripts/test_module_authorized_monster_hydration.py`
  - targeted combat regression coverage if encounter shape contracts are touched
- Systems affected:
  - combat encounter startup
  - module-authorized monster hydration path
  - enemy identity continuity across targeting, templates, AC backfill, prerolls, XP, and media
- Merge safety:
  - MUST keep helper-first changes in `utils/` and minimal `# TABLETOP MODE:` hooks in host files.
- SP/MP compatibility:
  - MUST preserve existing success behavior for exact local monster files.
  - MUST preserve single-player fallback behavior except where existing tabletop fail-closed authority boundaries already apply.

## Context

`createEncounter` currently routes monster names through `core/generators/combat_builder.py`, which in tabletop mode fail-closes when a local module monster JSON file is missing. That protection is useful against narration-only hallucinations, but it is too coarse when authored module content already establishes a creature as real for the current module. The `Night_of_the_Restless_Dead` failure demonstrates the gap: authored area/plot text clearly references `Cultist`, but the module lacks `modules/Night_of_the_Restless_Dead/monsters/cultist.json`, so live combat fails even though the threat is canon.

The design must preserve the existing anti-hallucination boundary:
- Python state and authored module files remain the authority.
- Runtime narration alone MUST NOT authorize new monsters.
- TABLETOP MODE hooks MUST remain minimal and merge-safe.

## Goals / Non-Goals

**Goals:**
- MUST distinguish `authorized but missing stat file` from `unauthorized monster` during encounter creation.
- MUST derive authorization from authored module content only.
- MUST allow deterministic or controlled hydration for authorized missing monsters.
- MUST preserve fail-closed behavior when authorization is missing, ambiguous, or hydration fails.
- SHOULD reuse existing monster files or standard monster seeds before invoking AI generation.
- SHOULD keep the runtime contract backward compatible once a monster JSON already exists.

**Non-Goals:**
- MUST NOT authorize monsters from freeform runtime narration or chat history alone.
- MUST NOT silently accept stronger substitute monsters such as `Cult Fanatic` when only `Cultist` is authored.
- MUST NOT redesign the full startup preflight system in this slice.
- MUST NOT replace module validation with runtime-only healing for all monster integrity issues.

## Decisions

### Decision: Use a module-authored authorization roster before monster loading
- MUST build an authorization roster from current module authored sources before allowing hydration.
- Candidate authoritative sources:
  - existing `modules/<module>/monsters/*.json`
  - explicit area/location creature fields
  - authored plot/area prose fields already shipped in module JSON where creature names are intentionally encoded
- SHOULD normalize names with the same slug rules used by combat monster lookup.

Rationale:
- This preserves Python-authored module truth as the gate.
- It allows canon creatures like `Cultist` to pass without letting runtime narration invent new enemies.

Alternatives considered:
- Trust runtime narration if the LLM describes the monster vividly -> rejected, too permissive.
- Keep current fail-closed behavior for all missing files -> rejected, blocks valid authored content during play.

### Decision: Split resolution into authorization, reuse, and hydration phases
- MUST evaluate monsters in this order:
  1. If local module monster JSON exists, use it.
  2. If monster is authorized by module content but missing locally, attempt reuse or hydration.
  3. If monster is not authorized, reject as hallucinated encounter content.
- SHOULD prefer deterministic reuse before AI generation:
  - copy/reuse an existing normalized monster JSON from a trusted module source when it is clearly the same standard monster
  - otherwise invoke controlled builder hydration

Rationale:
- Standard monsters like `Cultist` should not require a fresh LLM invention every time.
- Reuse-first lowers runtime risk and keeps outputs more stable.

Alternatives considered:
- Always generate with `monster_builder.py` for authorized monsters -> rejected, costlier and less deterministic.
- Auto-copy any same-slug monster file from anywhere without authorization gate -> rejected, risks cross-module leakage for non-canonical creatures.

### Decision: Keep failure classes explicit and operator-facing
- MUST surface at least two deterministic error classes:
  - `unauthorized_monster_reference`
  - `authorized_monster_hydration_failed`
- MUST preserve the existing createEncounter fail-closed path and system-visible error behavior.
- SHOULD include monster name, module, and expected target path in error output.

Rationale:
- Operators need to know whether to fix module content, add a monster file, or correct an LLM encounter response.

Alternatives considered:
- Collapse all failures to a generic missing monster error -> rejected, hides the actual recovery path.

### Decision: Keep host-file edits minimal and helper-driven
- MUST implement the authorization logic in isolated helper code rather than sprawling edits inside `combat_builder.py`.
- SHOULD keep `core/generators/combat_builder.py` as a thin caller over helper results, marked with `# TABLETOP MODE:` where needed.

Rationale:
- Merge safety and auditability remain intact.

## Risks / Trade-offs

- [Authorization heuristic too broad] -> Mitigation: only consume authored module JSON sources, never runtime narration.
- [Authorization heuristic too narrow] -> Mitigation: add regression cases for canonical module-authored creatures like `Cultist` in `Night_of_the_Restless_Dead`.
- [Reuse copies unintended variant stats across modules] -> Mitigation: reuse only same normalized standard-monster identities; fail closed for named/special variants unless explicitly authored.
- [Hydration still fails during live play] -> Mitigation: preserve explicit actionable error class `authorized_monster_hydration_failed` and do not emit combat-start narration.
- [Runtime behavior diverges from preflight expectations] -> Mitigation: keep startup preflight semantics unchanged in this slice and scope new behavior to encounter-time authorization only.

## Migration Plan

1. Add module-authorized monster roster helper and source normalization.
2. Integrate helper into combat monster resolution path before current tabletop fail-closed branch.
3. Add reuse-first resolution for standard monsters, then controlled hydration fallback for authorized misses.
4. Update createEncounter error reporting to distinguish unauthorized vs hydration-failed cases.
5. Add regression coverage for:
   - authorized `Cultist` in Night with missing local file
   - unauthorized `Cult Fanatic` in Night
   - clearly hallucinated runtime monster
6. Rollback strategy: revert helper integration and fall back to the current strict tabletop fail-closed behavior if authorization rules prove too permissive.

## Open Questions

- Which authored text fields should count as authoritative creature declarations beyond explicit `monsters` arrays and `creatures` fields?
- Should standard-monster reuse pull from a dedicated shared bestiary source if available, or from existing trusted module monster JSONs first?
- Should successful hydration persist immediately to the module monster directory during live play, or remain an encounter-scoped temporary artifact until later validation?

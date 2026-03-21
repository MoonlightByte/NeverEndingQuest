## Context

The current encounter pipeline already has the correct downstream identity split:
- `name` is used as the live encounter-facing identity for UI display, tooltips, and target matching.
- `monsterType` is used as the canonical mechanics/template key for monster JSON loading, AC backfill, prerolls, XP, and media selection.

The failure occurs before that split helps. Authorization currently evaluates the raw `createEncounter.monsters[]` label as if it must itself be the canonical authorized identity. That means a flavored label such as `Cultist Leader` fails even though `Cultist` is authored and mechanically sufficient.

This change inserts canonical resolution before authorization/hydration while preserving the authored-content authority boundary.

## Architecture Boundaries

### Resolver Layer (`utils/module_monster_authority.py`)

MUST:
- own canonical monster-reference resolution
- own authorization roster lookup
- own resolved-canonical hydration input selection
- return structured outcomes that explain exact, canonicalized, ambiguous, or unauthorized results

SHOULD:
- remain deterministic and helper-driven
- keep match logic explainable from tokens/slugs, not opaque score heuristics

### Combat Builder Layer (`core/generators/combat_builder.py`)

MUST:
- remain a thin caller over resolver results
- preserve encounter `name` as the flavored display/target label
- persist canonical `monsterType` from resolver output
- preserve existing fail classes and encounter-generation stop behavior on resolver failure

SHOULD:
- minimize host-file churn
- keep TABLETOP MODE edits clearly marked

### Prompt Layer (`prompts/system_prompt_compressed.txt`)

MUST:
- guide the narrator toward canonical statblock names in `createEncounter.monsters`

SHOULD:
- clarify that leader/title/color flavor belongs in `encounterSummary`

## Goals / Non-Goals

**Goals**
- MUST resolve flavored labels to canonical authored monster identities only when deterministic.
- MUST preserve exact stronger authorized identities (for example `Bandit Captain`) instead of degrading them to base species.
- MUST preserve split encounter identity (`name` display, `monsterType` canonical mechanics key).
- MUST fail closed for unresolved and ambiguous labels.
- MUST keep existing authorization boundary restricted to authored module sources.
- SHOULD preserve existing error classes and extend diagnostics conservatively.

**Non-Goals**
- MUST NOT authorize from narration/chat history.
- MUST NOT add module-by-module alias rules.
- MUST NOT infer stronger variants from weaker base species.
- MUST NOT refactor unrelated combat encounter update logic.

## Key Decisions

### Decision 1: Resolve before authorize

MUST:
- add `resolve_authorized_monster_reference(module_name, monster_name)`
- route `materialize_authorized_monster_file(...)` through the resolver
- return structured metadata at minimum:
  - `requested_name`
  - `requested_slug`
  - `canonical_name`
  - `canonical_slug`
  - `authorized`
  - `resolution_mode` (`exact`, `subset_unique`, `ambiguous`, `unauthorized`)
  - `sources`

Rationale:
- Centralizes matching, keeps `combat_builder.py` simple, and makes failure diagnostics testable.

### Decision 2: Use conservative deterministic matching

MUST evaluate in this order:
1. exact authorized slug match
2. exact stronger authorized label match remains exact
3. unique base-species canonical candidate whose normalized signal tokens are contained in the requested label
4. otherwise fail closed as ambiguous or unauthorized

MUST:
- fail closed when more than one candidate survives the same resolution tier
- never widen to a stronger variant unless it was explicitly authorized exactly

SHOULD:
- treat a small set of generic modifier tokens as non-authoritative for canonicalization only when that does not create ambiguity
- keep modifier handling local and documented

Rationale:
- Solves `Cultist Leader` while preventing permissive fuzzy matching.

### Decision 3: Preserve encounter identity split explicitly

MUST:
- keep encounter `name` equal to the original flavored label (with duplicate suffixing if needed)
- keep encounter `monsterType` equal to the canonical resolved identity
- keep duplicate suffixing keyed by display label, not canonical type

Rationale:
- Prevents `Cultist Leader` from collapsing into generic `Cultist_5` style names and preserves stable target names.

### Decision 4: Preserve failure classes, enrich reasons

MUST preserve:
- `unauthorized_monster_reference`
- `authorized_monster_hydration_failed`

SHOULD include reason detail such as:
- `no_canonical_match`
- `ambiguous_candidates`

Rationale:
- Operators need to know whether the fix is prompt wording, module content, or missing monster assets.

## Trade-offs

- Strict canonicalization is safer but may leave some flavorful labels rejected.
- Adding generic modifier-token handling improves resilience but increases the risk of overreach if token policy grows unchecked.
- Preserving the encounter identity split avoids downstream refactors, but only if tests lock the shape tightly.

## Migration Sequence

1. Lock contract tests first, including stronger-exact and ambiguity cases.
2. Implement resolver helper and structured result shape.
3. Route hydration through resolved canonical identity.
4. Update combat builder to persist flavored `name` and canonical `monsterType`.
5. Apply prompt nudge.
6. Run compile, focused tests, touched combat regressions, and OpenSpec validation.

## Rollback

- Revert resolver integration in `materialize_authorized_monster_file(...)` and `combat_builder.py`.
- Keep the new tests available as documentation of intended future behavior, or revert them alongside the resolver if they no longer describe active runtime behavior.
- The rollback target is the current exact-match fail-closed authorization path.

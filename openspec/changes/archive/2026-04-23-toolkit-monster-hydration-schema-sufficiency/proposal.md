# toolkit-monster-hydration-schema-sufficiency

## Why

`Murder_at_the_Drowning_Lass` is currently failing toolkit re-ingest convergence on one residual blocker class: `monster_schema_completion_gap`.

The concrete failure is `modules/Murder_at_the_Drowning_Lass/monsters/restless_spirit.json`, which exists locally but is schema-incomplete. It contains only descriptive metadata and is missing required monster fields such as `size`, `alignment`, and `armorClass`.

This is not just a late repair failure. The shared hydration path currently accepts three reuse classes without checking whether they are schema-sufficient:

- existing module-local monster files
- reused monster files from other modules
- raw bestiary entries copied from `data/bestiary/monster_compendium.json`

Because the local `restless_spirit.json` already exists, hydration returns `source="existing"` and never falls through to better recovery paths. The later readiness repair step then attempts to backfill from the compendium, but the matching compendium entry is also description-only, so convergence deterministically stalls.

## What Changes

### New Capabilities

- Define a shared monster-schema sufficiency gate for hydration precedence decisions.
- Define a deterministic fallback rule where schema-incomplete `existing`, `reuse`, or `bestiary` candidates are treated as insufficient rather than successful hydration.

### Modified Capabilities

- `homebrew-ingest-monster-materialization` SHALL require schema sufficiency before a shared hydration source is accepted as successful.
- `tt-module-authorized-monster-hydration` SHALL preserve runtime backward compatibility for valid existing files, but SHALL NOT treat schema-incomplete local or reused monster files as authoritative hydration success.

## Capability Scope

### MUST

- The shared hydration helper SHALL validate schema sufficiency before returning success for `existing`, `reuse`, or `bestiary` outcomes.
- Schema sufficiency SHALL, at minimum, cover `size`, `alignment`, and `armorClass` for the shared hydration decision.
- Schema-incomplete `existing` artifacts SHALL fall through to later recovery paths instead of short-circuiting hydration success.
- Schema-incomplete `reuse` artifacts SHALL be skipped rather than copied into the target module.
- Schema-incomplete bestiary entries SHALL NOT be treated as successful raw-copy hydration when generation is available.
- When generation is disabled and no schema-sufficient deterministic source exists, the helper SHALL fail closed with a structured blocker result.
- The change SHALL include regression coverage for the exact edge case: a compendium hit exists, but both the local artifact and compendium entry are schema-incomplete.
- The change SHALL include a canary proving `Murder_at_the_Drowning_Lass` no longer stalls specifically because malformed `restless_spirit.json` was accepted upstream as hydrated.

### SHOULD

- Shared reporting should preserve why a candidate was skipped, such as `schema_incomplete_existing`, `schema_incomplete_reuse`, or `schema_incomplete_bestiary`.
- The sufficiency helper should remain narrowly scoped and reusable across toolkit and runtime paths rather than duplicating field checks.
- Regression coverage should include at least one runtime-oriented shared-helper test so the boundary remains aligned across toolkit and encounter-time call sites.

## Non-Goals

- Expanding monster schema completion into broad heuristic field synthesis.
- Replacing the existing readiness repair pass with a new remediation system.
- Changing authorization rules for which monsters are allowed by authored module content.
- General refactoring of the toolkit convergence pipeline outside this blocker path.

## Impact

- Affected code:
  - `utils/module_monster_authority.py`
  - `scripts/homebrew_materialize_monsters.py`
  - targeted toolkit/runtime regression tests
- Affected workflows:
  - toolkit rebuild and re-ingest convergence
  - shared monster hydration for deterministic module materialization
  - runtime authorized monster hydration through the same helper
- Primary canary module:
  - `modules/Murder_at_the_Drowning_Lass`

## Risks

- A sufficiency gate that is too broad could reject legitimate backward-compatible monster files.
- A sufficiency gate that is too narrow would preserve the current false-success behavior.
- Shared-helper changes could unintentionally alter runtime encounter hydration semantics if not regression-tested.

## Fallback

- If schema sufficiency cannot be proven for a deterministic source, preserve fail-closed behavior and continue reporting structured hydration debt.
- If the canary module still carries unresolved content debt after the precedence fix, classify that residual debt explicitly rather than accepting malformed hydration success.

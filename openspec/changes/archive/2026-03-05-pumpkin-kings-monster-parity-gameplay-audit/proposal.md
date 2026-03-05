## Why

`The_Pumpkin_Kings_Curse` has heavy monster media coverage but severe monster JSON undercoverage in `modules/The_Pumpkin_Kings_Curse/monsters/`. In tabletop mode, combat builder is fail-closed for missing monster files, so monsters can appear in narration but fail to materialize as valid combatants.

This creates repeated playtest issues: narration/combat desync, encounter creation failures, and unreliable boss/minion spawning.

## What Changes

- Populate missing monster JSON files for all active area monster references in `The_Pumpkin_Kings_Curse`.
- Normalize slug parity between references, monster JSON filenames, and media filenames.
- Add gameplay audit tooling that validates module runtime integrity (not just schema) before playtest.
- Add an OpenCode skill contract for repeatable module gameplay audits.

### Missing monster slugs to create

- animated_scarecrow
- blight_tendril
- bloodshadow
- cornfield_shadow
- grain_wraith
- guardian_stone
- harvest_shade
- lantern_husk
- nest_lurker
- noose_wraith
- protective_shadow
- pumpkin_stalkers
- rope_strangler
- rune_scarred_vermin
- scarecrow_sentinel
- shadow_creeper
- stirge_swarm
- straw_blight
- straw_husk
- swarm_of_field_rats
- the_pumpkin_king

### Non-goals

- No combat engine refactors.
- No area topology rewrites.
- No broad narrative rewrite.

## Capabilities

### New Capabilities
- `tt-monster-json-parity`
- `tt-module-gameplay-audit-tooling`
- `tt-tabletop-monster-resolution-contract`

### Modified Capabilities
- None.

## Impact

- Affected gameplay content:
  - `modules/The_Pumpkin_Kings_Curse/monsters/*.json` (new files)
  - optional media alias additions under `modules/The_Pumpkin_Kings_Curse/media/monsters/`
- Affected tooling:
  - `scripts/audit_module_gameplay.py` (new)
  - `.opencode/skills/module-gameplay-audit/SKILL.md` (new)

# Module Data Git Fix Plan

## Status

- Lifecycle state: Completed and archived
- Priority: High
- Goal: Remove runtime gameplay state from tracked module content so Git installs remain update-safe
- OpenSpec archive: `openspec/changes/archive/2026-03-15-module-data-git-fix/`
- Verification artifact: `openspec/changes/archive/2026-03-15-module-data-git-fix/coverage_audit.md`

## Problem Statement

The fork currently tracks several module files that are also mutated during live gameplay. This creates dirty working trees during normal play, which blocks Git-based updates and risks turning tester installs into poisoned repos.

The three problem file classes are:

1. `modules/<module>/areas/*.json`
2. `modules/<module>/module_plot.json`
3. `modules/<module>/player_quests_<module>.json`

These files started as module content, but they now function as live state.

## Provenance of the Problem Files

### 1. Live area files

These are mutated during play, not just at build time.

- NPC/background movement writes updated area state:
  - `core/ai/action_handler.py`
- Location reconciliation writes updated monster state into area files when leaving locations:
  - `utils/reconcile_location_state.py`
- Combat/location systems write encounter state back into area files:
  - `core/managers/combat_manager.py`

### 2. Live module plot file

`module_plot.json` is updated when quests and plot points advance during gameplay.

- Plot progression write path:
  - `updates/plot_update.py`

### 3. Player quest journal projection

`player_quests_<module>.json` is generated from plot state and is not canonical authored content.

- Write path:
  - `utils/quest_player_formatter.py`

## Desired End State

Separate shipped module content from mutable runtime state.

### Track in Git as canonical module content

- `areas/*_BU.json`
- `module_plot_BU.json`
- `module_context.json`
- `map_*.json`
- `monsters/*.json`
- `media/**`
- seeds, manifests, validation/build artifacts that are intentionally part of shipped module content

### Do not track in Git as runtime state

- `areas/*.json`
- `module_plot.json`
- `player_quests_<module>.json`
- gameplay-generated backups and transient artifacts

### Runtime contract

- Live `areas/*.json` should be hydrated from tracked `areas/*_BU.json`
- Live `module_plot.json` should be hydrated from tracked `module_plot_BU.json`
- `player_quests_<module>.json` should be treated as fully derived runtime output and regenerated as needed

## Why This Fix Is Safe

The codebase already has most of the right architectural shape:

- startup can initialize missing live files from `_BU` templates:
  - `utils/startup_wizard.py`
- reset already restores live files from `_BU` templates:
  - `utils/reset_campaign.py`

This means the repo can move toward a clean split without inventing a new persistence model from scratch.

## Module Audit (Final)

Canonical `_BU` coverage for live area and plot families is complete across shipped modules:

- `Keep_of_Doom`
- `Night_of_the_Restless_Dead`
- `The_Pumpkin_Kings_Curse`
- `The_Thornwood_Watch`

Night canonical coverage completed and tracked:

- `modules/Night_of_the_Restless_Dead/areas/NIG001_BU.json`
- `modules/Night_of_the_Restless_Dead/module_plot_BU.json`

No remaining canonical backup blockers were found before tracking cleanup.

## Implementation Plan

### Phase 1: Canonical backup completion

Add missing tracked canonical backup files where they do not yet exist.

Required first target:

- `modules/Night_of_the_Restless_Dead/areas/NIG001_BU.json`
- `modules/Night_of_the_Restless_Dead/module_plot_BU.json`

Acceptance:

- Every shipped module has canonical `_BU` coverage for all live area and plot files.

### Phase 2: Git tracking cleanup

Update `.gitignore` and tracked file set so runtime state is not versioned.

Planned untracking targets:

- `modules/*/areas/*.json`
- `modules/*/module_plot.json`
- `modules/*/player_quests_*.json`

Important exception:

- keep `*_BU.json` tracked
- keep intentionally canonical module content tracked

Acceptance:

- Fresh clone still ships complete module content
- Mid-campaign gameplay no longer dirties tracked repo state through normal play actions

### Phase 3: Runtime hydration hardening

Review and harden the live-file initialization path.

Required checks:

- startup creates missing live `areas/*.json` from `*_BU.json`
- startup creates missing live `module_plot.json` from `module_plot_BU.json`
- missing `player_quests_*.json` is regenerated cleanly when needed

Acceptance:

- Fresh install and reset both produce playable live module state without requiring tracked live JSON files.

### Phase 4: Update-path validation

Validate that a Git install remains clean through normal play and can still update.

Test scenarios:

1. Fresh clone -> launch -> start module -> no tracked-file dirtiness from normal play
2. Advance plot -> live runtime files change, but tracked tree remains clean
3. Leave location / reconcile monsters / move NPCs -> tracked tree remains clean
4. Use GUI `[UPDATE]` on Git install -> fast-forward path remains available when no code edits exist

## Additional Cleanup

Remove obvious tracked cruft that is not legitimate repo content:

- `{'issues': ['Missing required directory: npcs', 'No area files found']}`

This file is stray output and should not remain in the root of the repository.

## Risks

### Risk 1: Missing hydration path for a module

If a module lacks `_BU` coverage or startup hydration misses a file, a fresh install may fail to bootstrap live state.

Mitigation:

- complete `_BU` coverage first
- verify startup/reset for all shipped modules before untracking live files

### Risk 2: Tooling still assumes tracked live files exist

Some utility or toolkit paths may directly read live files and assume they were shipped in Git.

Mitigation:

- keep runtime filenames unchanged
- only change their tracked/untracked status and initialization guarantees

### Risk 3: Validation artifacts mixed with runtime outputs

Some generated JSON files may need a second pass to clarify whether they are canonical build outputs or live runtime projections.

Mitigation:

- explicitly classify each tracked JSON family during implementation

## Execution Outcome

- `.gitignore` runtime boundary aligned for live area, module plot, and player quest runtime files.
- Targeted live runtime module JSON families are untracked from index.
- Canonical `_BU` backups remain tracked, including Night backups.
- Startup/reset/runtime hydration + derived quest regeneration hardening implemented and verified.
- Fresh-clone runtime cleanliness smoke and local ff-only update workflow verification both pass.
- OpenSpec final validation: valid; change is archive-ready.

## Deliverables

1. `.gitignore` update for runtime/live module files
2. `_BU` completion for missing shipped modules
3. Untracking commit for live runtime JSON files
4. Root cruft file removal
5. Verification notes confirming clean Git installs remain update-safe during play

## Success Criteria

- Git installs do not become dirty from ordinary gameplay actions
- Canonical shipped module content remains complete for fresh installs and testers
- Reset/startup still recreate live module state correctly
- GUI/in-app updater is no longer blocked by normal module-state mutation

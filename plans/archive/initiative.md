# Initiative Audit and Incremental Implementation Plan

## Purpose
This document captures:

1. How initiative currently works in the codebase.
2. Which prior multi-PC initiative additions already exist.
3. A small-scope Phase 1 implementation that preserves the current two-group combat flow and adds deterministic initiative ordering up front.
4. Follow-on phases for optional expansion to 3-group initiative.

## Current Initiative Architecture (As-Is)

### 1) Encounter creation initializes per-creature initiative
- `core/generators/combat_builder.py:323` assigns player initiative.
- `core/generators/combat_builder.py:352` assigns enemy initiative.
- `core/generators/combat_builder.py:382` assigns NPC initiative.

This per-creature initiative is currently the primary sequencing data.

### 2) Multi-PC startup already stores party-vs-enemy group initiative metadata
- `core/ai/action_handler.py:847` calls `roll_group_initiative()`.
- `core/ai/action_handler.py:854` stores `worldConditions.combatInitiative`.

This is currently used for opening context/narration, not as the full sequencing authority.

### 3) Multi-PC combat loop uses deterministic queue + phase gating
- Turn queue built in `core/managers/multi_pc_combat.py:339`.
- Queue sorted by initiative in `core/managers/multi_pc_combat.py:413`.
- `/end` triggers phase handoff in `core/managers/combat_manager.py:2815`.
- Enemy/NPC batch list comes from `get_remaining_enemies_for_round()` in `core/managers/combat_manager.py:2833`.

### 4) Prompting is already dynamic per turn (important)
This is not a monolithic one-shot prompt flow.

Current architecture is:
1. Static system rules prompt loaded once (compressed prompt file).
2. Per turn, Python injects dynamic state blocks (`LIVE TRACKER`, phase state, actor lists, HP/AC, dice pools, player action, required response).
3. LLM returns JSON response.
4. Python validates and applies state updates.

So dynamic prompt construction is already the runtime pattern and should remain the pattern.

## Existing Stub/Draft Additions Relevant to Initiative

### Active pieces
- `party_initiative`, `enemy_initiative`, `party_goes_first` fields exist in `core/managers/multi_pc_combat.py:173`.
- `roll_group_initiative()` exists in `core/managers/multi_pc_combat.py:1012`.
- Group initiative narrative helper exists in `core/managers/multi_pc_combat.py:1815`.

### Partial/inert pieces
- Group initiative does not currently own turn sequencing.
- Queue ordering still drives sequencing.
- No distinct NPC group roll exists yet.

### Draft inconsistencies to clean later
- Docstring in `core/managers/multi_pc_combat.py:1113` claims ignoring `current_turn_index`, while delegated implementation uses index-based traversal.
- `turn_window_text` is assembled in `core/managers/combat_manager.py:3392` but not consumed.

## Phase 1 Goal (Small Scope)

Preserve current 2-group flow and add initiative-driven phase start:

- Groups remain:
  - `DM_GROUP` (NPC + Enemy combined batch)
  - `PC_GROUP` (facilitator-controlled PC turns)
- At combat start:
  1. Python pre-rolls DM group initiative.
  2. Facilitator provides PC group roll result.
  3. Higher roll starts first.
  4. Tie default: `DM_GROUP` wins tie.
- Existing `/end` behavior remains for ending PC group phase.
- Existing batch DM processing remains intact.

This keeps scope minimal and does not force 3-group architecture immediately.

## Phase 1 Prompt Strategy (No Major Refactor)

### Decision
Do not split prompting into multiple prompt JSON files and do not replace the current prompt structure.

### Approach
- Keep `prompts/combat/combat_sim_prompt_multipc_compressed.txt` as static rules baseline.
- Keep per-turn dynamic context generation in Python.
- Add one dynamic section injected by Python each turn:

```text
=== INITIATIVE STATE ===
MODE: two_group_phase1
DM_GROUP_ROLL: <int>
PC_GROUP_ROLL: <int>
WINNER: <DM_GROUP|PC_GROUP>
ROUND_STARTS_WITH: <DM_GROUP|PC_GROUP>
CURRENT_PHASE: <ENEMY_PHASE|PC_PHASE>
```

- `CURRENT_PHASE` is authoritative for allowed actors and required response.

This is the smallest safe change and is merge-friendly with SP prompt alignment.

## Phase 1 Data Model

Use existing encounter JSON only. Do not create extra JSON files.

Add encounter fields:
- `initiativeMode: "two_group_phase1"`
- `initiativeRolls: {"dmGroup": int, "pcGroup": int}`
- `initiativeWinner: "dmGroup" | "pcGroup"`
- `roundStartsWith: "dmGroup" | "pcGroup"`
- `awaitingPcGroupRoll: bool`

Notes:
- Continue reading legacy `worldConditions.combatInitiative` if present.
- Encounter file remains source of truth for combat initiative state.

## Phase 1 Input Contract for Facilitator Roll

To avoid UI churn in Phase 1, add a command in combat loop:
- `/init <1-20>`

Behavior:
1. If `awaitingPcGroupRoll=true`, combat loop blocks normal resolution until valid `/init` is received.
2. On valid roll:
   - persist roll,
   - compute winner,
   - set `roundStartsWith`,
   - set first `CURRENT_PHASE` accordingly,
   - clear `awaitingPcGroupRoll`.
3. Invalid input returns usage hint and re-prompts.

## Phase 1 Implementation Plan

### 1) `core/ai/action_handler.py`
- Replace automatic party-vs-enemy startup handoff with Phase 1 init state creation:
  - Roll `dmGroup` initiative in Python.
  - Set `awaitingPcGroupRoll=true`.
  - Persist phase-1 initiative fields to encounter.

### 2) `core/managers/combat_manager.py`
- Add command parser support for `/init <roll>` in combat loop.
- Gate combat progression until PC roll is supplied when `awaitingPcGroupRoll=true`.
- Inject new `=== INITIATIVE STATE ===` block into per-turn dynamic prompt.
- On round boundary, set next round start phase from `roundStartsWith`.
- Preserve current `/end` semantics and DM_GROUP batch behavior.

### 3) `core/managers/multi_pc_combat.py`
- Keep queue and existing phase functions.
- Add minimal helper(s) if needed to set/reset phase deterministically from `roundStartsWith`.
- Do not perform major queue refactor in Phase 1.

### 4) Prompt files
Minimal text edits only:
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
  - Clarify ENEMY_PHASE may start from initiative winner at combat/round start, not only `/end`.
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
  - Accept ENEMY_PHASE starts when initiative state says so.

No structural prompt rewrite.

## Files Expected to Change in Phase 1

- `core/ai/action_handler.py`
- `core/managers/combat_manager.py`
- `core/managers/multi_pc_combat.py` (small helper-level edits)
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt` (small wording updates)
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt` (small validation updates)

## Phase 1 Acceptance Criteria

1. New encounters initialize two-group initiative state with `awaitingPcGroupRoll=true`.
2. Combat does not proceed until facilitator submits `/init <roll>`.
3. First acting phase matches initiative winner.
4. Existing DM batch resolution still processes all listed non-PC actors in one response.
5. Existing PC flow and `/end` handoff still work.
6. Round start phase is stable and deterministic per persisted `roundStartsWith`.
7. No extra JSON files were introduced.

## Phase 1 Test Scenarios

1. DM wins start:
   - DM roll 16, PC roll 11 -> first phase is ENEMY_PHASE, then PC phase.
2. PC wins start:
   - DM roll 9, PC roll 17 -> first phase is PC_PHASE.
3. Tie handling:
   - DM roll 14, PC roll 14 -> DM_GROUP starts (tie rule).
4. Command gating:
   - invalid `/init` values rejected; combat remains blocked.
5. Round continuity:
   - round N+1 starts with persisted `roundStartsWith`.
6. Backward compatibility:
   - old encounters without Phase 1 fields get safe defaults or migration path.

## Phase 2 (Optional, Future)

If desired later, expand to full 3-group initiative:
- separate `npc`, `enemy`, and `pc` group rolls,
- group order ranking each round,
- dedicated NPC batch then Enemy batch then PC group.

This remains deferred to keep Phase 1 small and low risk.

## Scope and Effort (Phase 1)

Phase 1 is small-to-medium scope:
- Mostly Python orchestration and state wiring.
- Minimal prompt text adjustments.
- No major prompt architecture refactor.

Estimated effort: about 0.5 to 1 focused day including validation tuning and regression checks.

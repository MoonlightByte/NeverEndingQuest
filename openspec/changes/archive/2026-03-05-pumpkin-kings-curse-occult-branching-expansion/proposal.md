## Why

The Pumpkin King's Curse already has a strong atmosphere, valid schema wiring, and a coherent PP001-PP007 progression. However, the current narrative is mostly linear and underuses the module's occult potential. It needs a deeper origin thread, stronger reason-led clue discovery, and multiple ending outcomes that are equally viable without breaking existing JSON contracts used by the LLM DM runtime.

The user requested a restrained "August Underground" influence: intense occult unease and moral dread, but not explicit gore-forward content.

## What Changes

- Add a restrained occult-horror layer across the existing module through additive clues, ritual evidence, and escalating omens.
- Add branching outcome design with equal-viability endings tied to player reasoning and side-quest completion.
- Add mixed-scope content updates:
  - Extend existing locations in HFG001, CMS001, BOO001, GRV001, HLF001.
  - Add selective new location nodes where needed for origin evidence and branch triggers.
- Add reason-first clue graph with bounded DCs (12-18) for ritual logic, pact interpretation, and ending unlocks.
- Keep all changes additive and contract-safe:
  - Preserve existing PP001-PP007 chain.
  - Preserve existing area IDs and core route connectivity.
  - Preserve action-handler compatible structures.

### Non-goals

- No schema refactors or key renames in existing module JSON.
- No combat engine or core runtime code changes.
- No UI redesign work.
- No shift to explicit splatter/gore tone.

## Capabilities

### New Capabilities
- `pumpkin-kings-occult-escalation`: restrained occult horror progression through environmental and ritual narrative evidence.
- `pumpkin-kings-branching-ending-parity`: multiple equal-viability endings with clear reasoning-based unlock paths.
- `pumpkin-kings-contract-safe-additive-expansion`: additive-only module data expansion preserving LLM DM JSON compatibility.

### Modified Capabilities
- None.

## Impact

- Affected data files (planned):
  - `modules/The_Pumpkin_Kings_Curse/module_plot.json`
  - `modules/The_Pumpkin_Kings_Curse/module_context.json`
  - `modules/The_Pumpkin_Kings_Curse/areas/VO001.json`
  - `modules/The_Pumpkin_Kings_Curse/areas/BOO001.json`
  - `modules/The_Pumpkin_Kings_Curse/areas/GRV001.json`
  - `modules/The_Pumpkin_Kings_Curse/areas/HLF001.json`
  - `modules/The_Pumpkin_Kings_Curse/areas/HFG001.json`
  - `modules/The_Pumpkin_Kings_Curse/areas/CMS001.json`
  - `modules/The_Pumpkin_Kings_Curse/player_quests_The_Pumpkin_Kings_Curse.json` (if needed for quest entries)
- Risk level: Medium (narrative branching and balancing), mitigated by additive-only edits and schema validation.
- Fallback strategy: keep original linear path fully playable if optional branch clues are missed.

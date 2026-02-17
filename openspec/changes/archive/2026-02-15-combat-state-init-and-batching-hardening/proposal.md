## Why

Recent tabletop combat logs show three coupled failures:

1. Combat is narrated as active even when formal encounter initialization fails.
2. `/init` and `/end` commands are inconsistently routed, sometimes leaking into narrator behavior outside active combat.
3. Enemy/NPC batch execution is inconsistent for PC-targeted damage, causing missing attacks on PCs.

Because these are state-machine issues, patching initiative or batch rules in isolation is not sufficient. The combat pipeline must fail closed, route combat-only commands deterministically, and keep initiative/batch rules authoritative once combat is active.

## What Changes

- Harden combat entry and validation retry behavior to fail closed when formal combat setup is invalid or incomplete.
- Add command-routing guards in narrative mode for combat-only slash commands (`/init`, `/end`, `/att`, `/dmg`, related aliases).
- Normalize Phase 1 two-group initiative startup state and remove legacy drift paths during active combat.
- Align enemy/NPC batch handling and combatant integrity checks so PCs are valid targets during enemy phase while remaining forbidden as DM-controlled actors.
- Add regression coverage for all four behaviors.

### Non-goals

- No rewrite of combat prompt architecture.
- No changes to core single-player narrative rules outside command guardrails.
- No new gameplay mechanics beyond startup/routing/batching correctness.

## Capabilities

### New Capabilities

- `combat-entry-fail-closed`: combat commitment paths reject invalid initialization and do not continue narrated combat in a non-combat state.
- `combat-command-routing-guards`: combat-only commands are blocked outside active combat and return deterministic system guidance.

### Modified Capabilities

- `multipc-two-group-initiative-start`: active combat startup consistently enforces Phase 1 two-group initiative state.
- `multipc-enemy-phase-batching-integrity`: enemy/NPC batch resolution supports PC targeting integrity and complete deterministic actor coverage.

## Impact

- Affected code:
  - `main.py`
  - `core/ai/action_handler.py`
  - `core/managers/combat_manager.py`
  - `core/managers/multi_pc_combat.py`
  - `scripts/test_multi_pc_combat.py` (and/or focused combat regression tests)
- User-visible behavior:
  - No more fake combat progression when encounter setup fails.
  - `/init` and `/end` become deterministic and context-correct.
  - Enemy phase reliably applies valid attacks/damage against PCs.
- Compatibility:
  - Additive and backward-compatible with existing tabletop plugin boundaries.

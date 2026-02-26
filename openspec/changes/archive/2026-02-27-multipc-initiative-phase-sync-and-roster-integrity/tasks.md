## 1. Phase Transition Contract (dmGroup Opening)

- [X] 1.1 Add additive opening-batch phase marker handling in `core/managers/combat_manager.py` for dmGroup starts (`/init` path and persisted round-start path).
- [X] 1.2 Implement deterministic enemy-opening-batch completion transition to `PC_PHASE` after first enemy batch resolves.
- [X] 1.3 Ensure phase, required-response prompt, and active-turn pointer remain coherent in runtime state (`core/managers/multi_pc_combat.py` and integration points).
- [X] 1.4 Add structured debug logging for phase marker set/clear and fallback paths.

## 2. Encounter Roster Integrity

- [X] 2.1 Update encounter generation in `core/generators/combat_builder.py` to include all Multi-PC `partyMembers` as player combatants.
- [X] 2.2 Add combat-start/resume normalization in `core/managers/combat_manager.py` to backfill missing player combatants from character files and party tracker.
- [X] 2.3 Ensure normalization is additive-only (no mutation of existing enemy/NPC HP/status/initiative except as explicitly required).
- [X] 2.4 Add fail-open error handling for missing/invalid character sources with clear diagnostics.

## 3. Initiative Payload Coherence

- [X] 3.1 Update initiative payload assembly in `web/extensions/tabletop_socket_handlers.py` to include player combatants while combat is active, including unconscious/incapacitated states.
- [X] 3.2 Preserve existing ordering and payload compatibility fields for frontend consumers.
- [X] 3.3 Verify UI no longer shows false missing-player state during active combat.

## 4. Regression Coverage

- [X] 4.1 Add focused tests for dmGroup opening enemy batch -> PC phase transition and non-loop behavior.
- [X] 4.2 Add tests for encounter roster backfill and duplicate-prevention when a player already exists.
- [x] 4.3 Add tests for initiative payload inclusion of unconscious/incapacitated players.
- [x] 4.4 Add compatibility tests confirming pcGroup starts and single-player behavior remain unchanged.

## 5. Verification and Apply Readiness

- [x] 5.1 Run syntax checks: `python3 -m py_compile` on modified Python modules.
- [x] 5.2 Run targeted regression suites for combat manager and tabletop initiative payload behavior.
- [x] 5.3 Perform smoke validation with one dmGroup-start encounter and one pcGroup-start encounter; confirm no phase/roster desync.
- [x] 5.4 Validate OpenSpec artifacts: `openspec validate multipc-initiative-phase-sync-and-roster-integrity`.

SHOULD notes (non-blocking):

- SHOULD keep all host file edits marked with `# TABLETOP MODE:` comments for merge clarity.
- SHOULD add minimal telemetry markers that help identify phase-source decisions without increasing prompt token load.

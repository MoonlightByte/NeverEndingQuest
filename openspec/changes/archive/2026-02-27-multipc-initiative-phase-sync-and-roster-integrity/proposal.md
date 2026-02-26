## Why

Multi-PC combat can enter a broken loop when initiative starts with `dmGroup`: enemy actions resolve, but phase state does not deterministically return to player control. At the same time, encounter files can contain only the triggering player instead of the full party roster, causing initiative/UI desync (missing PCs, invalid turn prompts, and repeated enemy narration against downed targets).

## What Changes

- Add a deterministic phase transition contract for `dmGroup` round starts.
  - **MUST** flip from opening `ENEMY_PHASE` back to `PC_PHASE` after the opening enemy batch completes.
  - **MUST** keep tracker pointer and phase state aligned so prompts cannot claim both "PC current turn" and "enemy-only phase" at once.
  - **SHOULD** record explicit transition markers in encounter state and debug logs for observability.
- Enforce encounter roster integrity for Multi-PC combat.
  - **MUST** ensure all `partyMembers` are present as `type: "player"` combatants in encounter data.
  - **MUST** backfill missing player combatants on combat start/resume without dropping existing enemy/NPC state.
  - **SHOULD** preserve existing initiative values when possible and use safe defaults only for newly backfilled entries.
- Align initiative UI payload behavior with combat truth.
  - **MUST** include relevant player combatants (including incapacitated/unconscious) in initiative payloads while combat is active.
  - **SHOULD** keep sorting/display behavior unchanged except where required to avoid false "missing PC" states.
- Add regression coverage for `dmGroup` opening-phase transitions and roster backfill behavior.

Non-goals:
- No redesign of the full combat architecture, action grammar, or LLM provider routing.
- No schema-breaking changes to existing encounter format beyond additive fields/normalization.
- No changes to single-player behavior beyond required compatibility guards.

## Capabilities

### New Capabilities
- `tt-combat-phase-sync`: Deterministic phase transitions for `dmGroup` starts and per-round state coherence between phase, tracker pointer, and prompt contract.
- `tt-combat-roster-coherence`: Guaranteed Multi-PC player roster presence in encounter/runtime/UI initiative surfaces, including recovery from partial encounter state.

### Modified Capabilities
- None.

## Impact

- Affected runtime modules:
  - `core/managers/combat_manager.py`
  - `core/managers/multi_pc_combat.py`
  - `core/generators/combat_builder.py`
  - `web/extensions/tabletop_socket_handlers.py`
- Affected state files and flow:
  - `modules/encounters/encounter_*.json`
  - `party_tracker.json` combat lifecycle fields
  - `modules/conversation_history/combat_conversation_history.json` prompt coherence
- Risk and rollout:
  - Primary risk is turn-order regression if phase flip timing is wrong.
  - Mitigation: additive state markers, explicit transition guards, targeted regression tests, fail-open fallback to existing behavior if new marker absent.
- Merge-safety and compatibility:
  - Host-file edits remain minimal and marked with `# TABLETOP MODE:` comments.
  - Multi-player path is targeted; single-player compatibility is preserved by runtime guards.

## Why

Multi-PC combat has regressed into a state-coherence failure where mixed-form party identities, stale active-actor selection, dead-target reuse, and incomplete death-save persistence contaminate the combat prompt and desynchronize runtime truth from narration. This now produces visible gameplay breakage: unconscious PCs can act, already-dead cultists keep getting attacked, enemy damage is applied without coherent narration, and death saves are requested but not durably preserved.

This needs a focused repair now because the failure crosses prompt assembly, fast-lane command routing, encounter state, and character persistence. Left unresolved, each local bugfix risks masking the underlying state split instead of restoring a single authoritative combat contract.

## Objective

Restore deterministic multi-PC combat coherence so canonical party identity, active-turn ownership, living target selection, incapacitated-turn handling, and death-save persistence all agree across command routing, prompt generation, encounter state, and character storage.

## What Changes

- Add canonical party-member dedupe at multi-PC combat initialization and resume so mixed-form labels do not create duplicate player combatants.
- Tighten active-PC synchronization so prompt actor, selected party tab, turn queue, and required-response contract all reference the same acting PC.
- Exclude dead and otherwise inactive enemies from player-phase turn windows and local target resolution.
- Make local `/att` and `/dmg` targeting prefer living canonical matches instead of reusing dead enemies by partial-name precedence.
- Block incapacitated PCs from attack/damage command resolution and force death-save flow on their turn.
- Add deterministic death-save persistence support so death-save success/failure updates survive schema validation and crash/resume recovery.
- Preserve single-player compatibility and existing fast-lane command UX where the acting combatant is valid and conscious.

## Non-Goals

- This change MUST NOT redesign the broader combat prompt architecture.
- This change MUST NOT replace fast-lane combat commands with a new command system.
- This change MUST NOT broaden NPC roster rules beyond current tabletop party and encounter semantics.
- This change MUST NOT change 5e death-save rules or introduce new combat mechanics.
- This change MUST NOT require a new external dependency or storage backend.

## Capabilities

### New Capabilities
- `tt-combat-death-save-persistence`: Death-save outcomes SHALL persist deterministically and SHALL remain coherent with incapacitated-turn handling.

### Modified Capabilities
- `tt-combat-roster-coherence`: Multi-PC combat roster normalization SHALL dedupe canonical party identity and SHALL avoid dead-target leakage into player-facing combat state.
- `tt-combat-phase-sync`: Active actor selection, prompt contract, and turn ownership SHALL remain coherent across manual PC switching and fast-lane command handling.
- `tt-combat-request-roll-routing`: Unconscious active PCs SHALL be routed into death-save request flow and resumed death-save resolution instead of ordinary action flow.
- `tt-deterministic-character-ops-application`: Deterministic character ops SHALL support death-save persistence without schema purge or silent prose fallback loss.

## Risks

- Canonical dedupe could collapse legitimately distinct identities if normalization is too broad.
- Active-actor synchronization changes could regress valid manual switching if queue ownership and selected PC are not reconciled carefully.
- Death-save persistence changes could conflict with legacy validation or repair passes if schema and runtime support are only partially updated.
- Tightened incapacitated-command guards could block valid resume flows if death-save routing is not in place first.

## Fallback

- If deterministic death-save ops support proves unsafe, rollback SHALL preserve the new incapacitated-command guard while temporarily routing death-save persistence through a narrow legacy-safe path.
- If active-actor synchronization changes regress turn flow, rollback SHALL preserve roster dedupe and dead-target filtering while reverting the queue-selection coupling.
- Existing single-player combat behavior MUST remain compatible throughout rollout.

## Impact

- Affected code:
  - `core/managers/multi_pc_combat.py`
  - `core/managers/combat_manager.py`
  - `updates/update_character_info.py`
  - `schemas/char_schema.json`
  - targeted combat regression suites under `scripts/`
- Systems affected:
  - multi-PC combat startup/resume normalization
  - fast-lane `/att` and `/dmg` routing
  - prompt actor and turn-window generation
  - death-save request and persistence path
  - crash/resume combat recovery integrity
- Merge safety:
  - MUST keep helper-first changes localized and preserve minimal `# TABLETOP MODE:` hooks in host files.
- SP/MP compatibility:
  - MUST preserve single-player behavior.
  - MUST preserve normal conscious-PC fast-lane combat flow in tabletop mode while preventing incapacitated misuse.

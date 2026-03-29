## Why

Multi-PC combat can leave enemies in an impossible ghost state: the encounter file, turn queue, target resolver, and initiative UI disagree about whether a hostile is still alive. This produces bad tabletop UX such as negative-HP enemies remaining visible in initiative, `/att` reporting `Target ... not found`, and fast-lane `/dmg` updates drifting from later LLM-driven `updateEncounter` writes.

This needs a focused fix now because the issue is mechanically misleading during live combat and undermines player trust in Python-enforced combat truth.

## What Changes

- Add one authoritative defeated-enemy convergence path so enemy HP/status cannot remain mechanically alive after reaching 0 HP or below.
- Normalize enemy encounter updates so Python clamps hostile HP to 0 and assigns a schema-legal defeated status when defeat is implied.
- Ensure initiative UI and local combat targeting exclude defeated/non-living enemies using the same mechanical truth as the encounter state.
- Resync or rebuild the in-memory non-PC turn queue after immediate encounter-state mutations so queue targeting and visible initiative state cannot drift from persisted encounter data.
- Harden the fast-lane `/dmg` follow-up contract so immediate Python-applied enemy damage is not effectively double-applied or contradicted by later LLM encounter updates.

Non-goals:
- No redesign of combat narration style, initiative ordering rules, or DM-group opening-batch behavior.
- No change to player visibility rules that keep unconscious PCs present in initiative.
- No expansion of structured encounter ops beyond what is needed to preserve defeated-enemy truth.

Rollout risk and fallback:
- MUST preserve single-player compatibility and existing multi-PC turn-flow semantics.
- MUST fail closed on impossible enemy-state contradictions only where mechanics would otherwise become misleading.
- SHOULD keep narration fail-open where possible, but Python mechanical state MUST remain authoritative even if narration lags.

Merge-safety and compatibility impact:
- MUST keep host-file edits minimal and TABLETOP MODE-marked.
- MUST preserve backward compatibility with existing encounter files and legacy combat flows.
- SHOULD prefer additive normalization/resync helpers over broad combat-manager rewrites.

## Capabilities

### New Capabilities
- `tt-combat-defeated-enemy-state-sync`: authoritative convergence of defeated enemy HP/status across encounter persistence, local target resolution, turn queue state, and initiative UI visibility.

### Modified Capabilities
- None.

## Impact

- Affected runtime: `core/managers/multi_pc_combat.py`, `core/managers/combat_manager.py`, `updates/update_encounter.py`, `web/extensions/tabletop_socket_handlers.py`.
- Affected behavior: fast-lane `/att` and `/dmg`, enemy defeat persistence, initiative queue visibility, local target resolution.
- Affected tests: targeted combat regression coverage for defeated-enemy UI visibility, queue sync, and duplicate-damage prevention.
- No external API or dependency changes expected.

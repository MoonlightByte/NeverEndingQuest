## Context

TABLETOP MODE currently has three enemy-state views during combat: the persisted encounter file, the in-memory multi-PC turn queue, and the initiative payload exposed to the web UI. Those views can diverge after fast-lane `/dmg` updates and later LLM-driven `updateEncounter` writes, especially when enemy HP drops to 0 or below without a matching defeated status normalization.

The current failure shape is consistent:
- Encounter state can retain `currentHitPoints <= 0` with `status="alive"`.
- `find_target(...)` rejects that enemy because the in-memory target resolver treats `hp <= 0` as inactive.
- Initiative UI can still display that enemy because non-player visibility currently keys off `status == "alive"` only.
- The turn queue can keep stale non-PC HP/status until combat startup rebuild or manual progression eventually masks it.

This is cross-cutting enough to justify a design document because the fix touches persistence normalization, queue synchronization, local combat commands, and UI visibility contracts.

## Goals / Non-Goals

**Goals:**
- MUST establish one authoritative enemy defeat convergence rule across encounter persistence, turn queue state, target resolution, and initiative UI payloads.
- MUST prevent negative-HP or zero-HP enemies from remaining targetable or visible as living combatants.
- MUST preserve fast-lane `/att` and `/dmg` responsiveness while ensuring Python-applied mechanical state remains authoritative over later narration-side writes.
- MUST preserve single-player compatibility and existing multi-PC initiative/phase behavior.
- SHOULD keep host-file edits small and TABLETOP MODE-marked.

**Non-Goals:**
- No changes to combat narration style, enemy tactics, or initiative pacing.
- No redesign of `updateEncounter` prompt contracts beyond what is required to preserve authoritative enemy defeat truth.
- No change to the player-side rule that unconscious PCs remain visible in initiative.

## Decisions

### Decision: Encounter finalization is the authoritative enemy defeat normalizer
- MUST normalize enemy HP/status inside `updates/update_encounter.py` before validation/persist.
- MUST clamp enemy `currentHitPoints` to `0` minimum.
- MUST assign a schema-legal defeated status when enemy HP resolves to `0` or below.
- SHOULD prefer a single helper-based normalization path so ops-based and prose-fallback encounter updates converge through the same rule.

Rationale:
- `update_encounter.py` is already the authoritative Python write path for enemy mechanics.
- Fixing defeat semantics there prevents stale negative-HP alive-state from reaching disk and spreading into prompt/UI consumers.

Alternatives considered:
- Normalize only in UI filtering: rejected because it would hide ghosts visually while leaving target resolution and persistence inconsistent.
- Normalize only in `multi_pc_combat.py`: rejected because LLM-driven encounter updates can still write stale enemy state later.

### Decision: Multi-PC turn queue SHALL resync from authoritative encounter enemy state after immediate encounter mutation
- MUST refresh non-PC queue HP/status after immediate `updateEncounter` application in `core/managers/combat_manager.py`.
- SHOULD use a narrow resync helper rather than rebuilding unrelated PC state.
- MUST preserve existing PC phase ownership and active-character state when only enemy/NPC queue entries are refreshed.

Rationale:
- The queue currently behaves like a cached view. Without resync, targeting and progression can keep stale combatant state even after encounter persistence is corrected.

Alternatives considered:
- Full queue rebuild after every action: rejected as unnecessarily invasive and higher risk to active-PC/phase coordination.
- No queue resync and rely on next combat startup: rejected because the bug occurs during the same live combat session.

### Decision: Initiative UI SHALL apply the same living/non-living rule as target resolution for non-player combatants
- MUST exclude non-player combatants from `initiative_data_response` when status is non-living or `currentHitPoints <= 0`.
- MUST continue including non-dead player combatants, including unconscious/incapacitated PCs.
- SHOULD treat the initiative endpoint as a read-only truth consumer, not the primary normalization layer.

Rationale:
- The UI should not advertise an enemy as present when local commands already consider it defeated.
- Preserving the special PC visibility rule avoids regressing death-save UX.

Alternatives considered:
- Key all visibility off status only: rejected because HP can drift stale even when status is wrong.
- Key all visibility off HP only: rejected because PCs intentionally remain visible at 0 HP while unconscious.

### Decision: Fast-lane `/dmg` is the immediate mechanical authority for locally applied enemy damage
- MUST treat `/dmg` mutations in `multi_pc_combat.py` as committed enemy HP/status truth for that moment.
- MUST prevent later same-turn narration-side encounter updates from leaving the enemy in a mechanically living ghost state.
- SHOULD preserve narration fail-open, but Python truth MUST win when duplicate or contradictory follow-up writes occur.

Rationale:
- `/dmg` exists specifically to let players resolve hits immediately and keep combat moving.
- The builder should preserve that UX while preventing double-application or stale-state rollback.

Alternatives considered:
- Remove LLM follow-up after `/dmg`: rejected because narration continuity still matters.
- Let LLM remain authoritative after `/dmg`: rejected because it recreates the exact drift this change is fixing.

## Risks / Trade-offs

- [Risk] Legacy encounters may contain malformed enemy HP/status combinations. -> Mitigation: normalize additively and fail open where possible, but persist corrected state before the next UI/queue read.
- [Risk] Queue resync could disturb active PC ownership if implemented as a full rebuild. -> Mitigation: limit refresh scope to non-PC combatants and preserve existing PC/phase fields.
- [Risk] Status normalization could change downstream assumptions about `dead` vs `defeated`. -> Mitigation: use existing schema-legal vocabulary and keep the chosen status consistent across persistence/UI/targeting.
- [Risk] Fast-lane `/dmg` plus later `updateEncounter` may still describe stale narration text. -> Mitigation: prioritize Python mechanical truth and allow narration to lag rather than corrupt state.

## Migration Plan

- Step 1: Add enemy defeat normalization helper(s) in `updates/update_encounter.py` and route all encounter writes through them.
- Step 2: Add post-encounter-update non-PC queue resync in `core/managers/combat_manager.py` and/or `core/managers/multi_pc_combat.py`.
- Step 3: Tighten initiative payload filtering for non-player combatants in `web/extensions/tabletop_socket_handlers.py`.
- Step 4: Harden fast-lane `/dmg` no-ghost contract and add regression coverage.
- Step 5: Run targeted combat regression suites and manual smoke checks for `/att`, `/dmg`, defeated enemy visibility, and targeting after defeat.

Rollback:
- MUST be limited to reverting the additive helpers/hooks for this change.
- SHOULD leave encounter files schema-compatible even if the resync/UI filters are rolled back.

## Open Questions

- Which schema-legal defeated status should be preferred for non-undead ordinary enemy defeats in this flow: `dead` only, or `dead`/`defeated` depending on cause? The implementation should choose one deterministic rule and use it consistently.
- Should same-turn duplicate enemy damage be blocked strictly, or merely normalized so final HP/status truth cannot regress? The builder can choose the narrower approach if it preserves the MUST contract above.

# Typed Combat Pipeline

Purpose: Turn one persisted actor window into structured intent, committed mechanics,
restart-safe delivery, and player-facing narration.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

## Safety worktree delta (2026-09-05; live acceptance pending)

Combat provider calls use required transport and preserve typed supersession
through validators, orchestrator, manager and main handoff. Cancellation is not a
player-roll pause or a retryable semantic failure. Genuinely unowned combat entry
owns a scope/invocation lifetime; ordinary and recursive callers lend theirs.
Post-combat T082/T067 work remains fenced until the actual next input boundary.

Dice, actors, actions, reactions, HP/resources, XP, voice maps and encounter
schemas are unchanged by this harness repair. Ratified T097 completed-invalid
handling remains distinct from transport retry. Development checks are not proof
of P1-P9 live combat acceptance, which remains outstanding.

## Authority table

| Datum | Single source of truth | Commit or acceptance point |
|---|---|---|
| Scene participants, relations, objectives | `encounter_*.json.sceneFacts` | T067 scene is exact-key reconciled before builder publication |
| Controllers | `encounter_*.json.combatState.controllers` | Builder writes the reconciled controller map |
| Active encounter | `party_tracker.json.worldConditions.activeCombatEncounter` | History, tracker, then encounter activation receipt |
| Round, order, cursor, acted set | `encounter_*.json.combatState` | `begin_turn`; advance only in `commit_turn` |
| HP, resources, conditions | Character JSON for player/NPC; encounter state for monsters | Staged absolute events apply under ordered leases; encounter receipt writes last |
| Dice reserve | Encounter `preroll_cache` | Reserve before intent; consumption joins the staged receipt |
| Player roll or clarification | `combatState.pendingTurn.playerExchanges` | Accepted input persists beside the same `turnId` |
| Undelivered committed beat | `combatState.pendingDelivery` | Narration records after mechanics; durable display precedes acknowledgment |
| Combat transcript | `modules/conversation_history/combat_conversation_history.json` | `_combatDeliveryId` marker persists before receipt clear |
| Completion and rewards | `combatState.completion`, character XP, area summary, archive | Exit clock, XP, summary, archive, tracker clear, closed receipt |

## Flow

### New typed encounter and opening

1. T067 emits `createEncounter.scene`; the builder reconciles canonical participant keys.
2. Activation publishes matching combat history, party tracker identity, and encounter receipt.
3. T044 returns opening narration with no combat actions.
4. T040 validates the opening candidate.
5. Accepted or truthful fallback prose is persisted and displayed; phase becomes
   `awaiting_actor`.

### Actor window

1. The manager derives the exact actor-ID window and persists `pendingTurn`.
2. On the voices branch, an actor-window T105 batch is collected before T096; main at this
   pin has no typed combat voice stage.
3. T096 selects one ordered structured intent per claimed actor. Corrections reuse the same
   turn claim.
4. `resolve_claimed_window` validates and resolves mechanics without provider authority.
5. Transaction code stages events and preimages, then applies character files and writes the
   encounter commit/cursor last.
6. T097 receives committed events and authoritative facts; it cannot mutate mechanics.
7. If a round closed, T042 may compress completed old rounds.
8. History receives the delivery marker, output is displayed, then `acknowledge_delivery`
   clears the receipt and the next window may begin.

### Resume

1. Matching history with no pending receipt uses T043 for narration-only re-engagement.
2. `intent_pending` resumes at T096 on the existing claim.
3. `events_staged` replays the staged absolute postimage, then continues at T097.
4. `pendingDelivery` skips T096 and mechanics; it reuses recorded narration or calls T097,
   then delivers and acknowledges exactly once.
5. `recovery_action` chooses the branch from persisted state, never from narration.

### Completion and handoff

1. The final T097 delivery is persisted, displayed, and acknowledged.
2. Completion exits the combat effect clock and applies XP once.
3. T041 builds the combat summary; area/history summary receipts are persisted.
4. The deterministic transcript archive is written before active combat is cleared.
5. `action_handler` emits the historical no-reapply record and `needs_post_combat_narration`.
6. Main rebuilds authoritative history and T067 handles the immediate post-combat beat.

## State and atomicity

- Encounter: `modules/encounters/encounter_<id>.json`; scene, turn receipts, events,
  delivery, initiative, prerolls, and completion.
- Party: `party_tracker.json`; active encounter identity and module/location context.
- Characters: canonical JSON paths from `ModulePathManager`; player/NPC postimages.
- Transcript: `modules/conversation_history/combat_conversation_history.json`.
- Per-file persistence uses `safe_write_json`. Cross-file turn safety is staged-event replay,
  ordered leases, precondition revalidation, applied-ID idempotence, and encounter-last commit.
- Activation publishes history -> tracker -> encounter receipt under the transition lock.
- Completion is a resumable sequence of reward, summary, archive, tracker-clear, and close receipts.

## Load-bearing seams

1. `core/combat/scene.py:71` - exact-key scene reconciliation.
2. `core/generators/combat_builder.py:570` - new typed encounter construction.
3. `core/managers/combat_state.py:448` - conditional activation publication.
4. `core/managers/combat_state.py:727` - durable turn claim.
5. `core/managers/combat_state.py:855` - cursor advance and pending delivery.
6. `core/managers/combat_state.py:924` - restart recovery classifier.
7. `core/managers/combat_transaction.py:806` - staged events and preconditions.
8. `core/managers/combat_transaction.py:1160` - lease-protected exact-once apply.
9. `core/managers/combat_orchestrator.py:949` - typed turn coordinator.
10. `core/managers/combat_manager.py:3615` - T043 resume/pending-receipt split.
11. `core/managers/combat_manager.py:3840` - T044 opening; T040 follows in validation.
12. `core/managers/combat_manager.py:4507` - manager-to-orchestrator entry.
13. `core/managers/combat_manager.py:4652` - history-backed display and acknowledgment.
14. `core/managers/combat_manager.py:2129` - completion, rewards, summary, archive, clear.
15. `main.py:6195` - post-combat T067 handoff.

## Invariants

- #193 Part 2, Combat.
- #193 Part 2, Save/restore/reset.
- #193 Part 2, Provider routing and startup.
- #193 Part 2, Schema and backward compatibility.
- #193 Part 5, D-VR-15; No-Limits; Single-Path; Fork-1a; D-LCR-1..3.
- #193 Part 5 open decisions D-4, D-5, D-6, and D-8 remain owner-only.

### Legacy residue

This revision still selects typed combat for agentic provenance and otherwise reaches T045.
That is current code, not the target architecture. #193 Part 5 Fork-1a retires T045 in favor
of forward adaptation into this typed pipeline; #266 is a hard retirement prerequisite.

## Open items

- #191 - agentic combat recovery epic.
- #201/#202/#243/#270 - lifecycle, lock, supersession, and command-arbitration gaps.
- #203/#205/#206/#207 - out-of-turn, unsupported-action, flee, and reinforcement gaps.
- #242/#245/#264/#266 - down scene, survivability, escape, and defensive-save parity.
- #253 - completed encounter source identity can duplicate fights and XP.
- #259/#268/#269 - combat voice delivery and player-roll restart gaps.
- #262 - remaining gameplay-path No-Limits retirement.
- #267 - T045 continuation defect; do not extend the retirement-bound runtime.

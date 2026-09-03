# Progression and Leveling

Purpose: award combat XP exactly once to participating character sheets, expose cumulative XP against the next threshold, and perform advancement through a separate agentic level-up conversation.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

## Authority table

| Datum | Source of truth | Acceptance or commit point |
|---|---|---|
| Defeated enemies | Active encounter and typed completion state | Combat completion classifier |
| XP value | Code-owned CR-to-XP table | Defeated-enemy total divided across tracker party members and NPCs |
| Reward recipients | Exact player/NPC character paths derived from encounter combatants | Enemy templates remain read-only |
| Reward idempotence | `completion.pendingRewards` and `completion.rewardsApplied` | Character absolute values write first; encounter receipt writes last |
| Current XP | Character JSON `experience_points` | Level-up code removes any attempted XP change |
| Level and threshold | Character JSON `level` and `exp_required_for_next_level` | Whole validated character update commits |
| Trigger and consent | Accepted T067 `levelUp` action under system/validation prompt contract | Player is asked first; eligible party NPC is intended to advance automatically |
| Advancement choices | T047 `LevelUpSession` conversation | Player interview or same-agent NPC automatic choice |
| Rules verdict | Exact T048 `{valid,errors,warnings,recommendation}` | Structural parser plus model verdict precede mutation |
| Final sheet | Canonical character JSON | T079-derived complete delta passes schema and atomic file replacement |

## Flow

1. Typed combat reaches all-hostiles-resolved and enters idempotent combat completion.
2. XP calculation loads the active encounter and party tracker. Each dead, defeated, or unconscious enemy contributes the CR table value; integer division produces XP per party member and party NPC.
3. Reward application takes ordered encounter and character leases. If `rewardsApplied` is already true, it exits without another award.
4. First application records each recipient's absolute `before` and `after` XP in `pendingRewards` and persists the encounter journal before changing a character.
5. It writes each character's absolute `after`, then sets `rewardsApplied=true`, clears `pendingRewards`, and writes the encounter receipt last. Replay converges without additive duplication.
6. Completion appends the XP narrative to ordinary history and finishes summary/archive receipts before clearing the active encounter.
7. Ordinary DM context exposes each party character's level, XP, and next threshold. The prompt instructs T067 to ask a player before emitting `levelUp`, while an eligible party NPC should advance automatically, one level at a time.
8. Main intercepts the first accepted `levelUp` action before ordinary narration/action handling and starts a `LevelUpSession`.
9. The action handler loads the named character and passes current/new level to the session. It does not itself evaluate XP eligibility, consent, or `newLevel == currentLevel + 1`; those are prompt/T048 responsibilities.
10. The session reloads the current module character; the player-versus-NPC split is decided by the T047 model reading `character_type` from the injected sheet under the shared prompt (`prompts/leveling/level_up_system_prompt.txt:16-17`), not by session-side branching (`is_player` at `level_up_manager.py:115` is computed but never read).
11. It initializes a separate conversation with the leveling prompt, full leveling reference, current sheet, and requested level transition.
12. T047 produces intermediate questions or a final `updateCharacterInfo`. Player questions are displayed and answered one at a time; NPC instructions request a complete final action on the initial T047 call.
13. Every T047 assistant turn is persisted to `level_up_conversation.json` before validation or mutation.
14. A final action goes to T048 with the current sheet, leveling reference, and proposed JSON. A rejected result receives one immediate T047 correction and another T048 check; a second rejection leaves a corrective message in the still-open session.
15. On acceptance, code extracts the changes and removes `experience_points`, preserving cumulative XP.
16. `update_character_info` takes its character locks, reloads the sheet, asks T079 for a typed delta, checks requested-field completeness and the character schema, and atomically replaces the file. Post-save smart validators may apply a second atomic correction.
17. Success marks the in-memory session complete and main appends one compact completion record. Failure appends a visible system failure, then returns control to the ordinary outer turn.

## State and atomicity

- `party_tracker.json` owns active encounter identity and party membership.
- The encounter JSON owns `pendingRewards` and `rewardsApplied`. XP award spans multiple files, but the pending absolute postimages make crash replay convergent.
- Character JSON owns cumulative XP, current level, next threshold, and all advancement mechanics. Individual writes are atomic; the broader level-up is not a `StateTransactionCoordinator` transaction.
- `level_up_conversation.json` is overwritten after each interview turn. A new session does not reload it, so it is an audit trace rather than restart authority.
- Main conversation history owns the player-visible opening, completion, and failure records.
- Character updates create backups but proceed if backup creation fails and use a bounded character path lease. Issue #152 tracks the missing coordinator transaction.
- `LevelUpSession` is process-local. EOF aborts visibly; retry creates a new session.
- The schema requires integer level, current XP, and next threshold but sets no min/max there. The ordinary DM validator constrains level 1 through 20; the action entrant only checks required action fields.
- The leveling reference lists thresholds from level 1 onward. It ends with wording that conflicts with the system prompt and code about changing current XP; code's deterministic removal makes cumulative-XP preservation authoritative.
- The per-encounter receipt prevents duplicate award within one encounter identity. Issue #253 tracks duplicate semantic encounters created under a new identity.

## Load-bearing seams

1. `utils/xp.py:10-30` - CR-to-XP table and normalization.
2. `utils/xp.py:35-112` - defeated-enemy accounting and party division.
3. `core/managers/combat_manager.py:1555-1580` - exact recipient character paths.
4. `core/managers/combat_manager.py:2129-2205` - completion, XP history, and summary.
5. `core/managers/combat_transaction.py:1266-1309` - reward journal and receipt-last writes.
6. `schemas/encounter_schema.json:532-549` - completion receipt schema.
7. `schemas/char_schema.json:24-26` and `schemas/char_schema.json:519-548` - progression fields.
8. `prompts/system_prompt.txt:965-983` - player consent and NPC advancement contract.
9. `core/ai/action_handler.py:3681-3718` - `levelUp` entrant and session creation.
10. `main.py:4935-4976` - level-up interception before ordinary action output.
11. `core/managers/level_up_manager.py:75-138` - session load and T047 turns.
12. `core/managers/level_up_manager.py:140-259` - T048-before-update and cumulative-XP preservation.
13. `core/managers/level_up_manager.py:261-404` - conversation persistence, calls, and verdict parser.
14. `main.py:8982-9069` - interactive subloop and outer-history publication.
15. `updates/update_character_info.py:1323-1358` and `updates/update_character_info.py:2142-2216` - downstream update boundary.

## Invariants

- See #193 Part 1 for B1/B2, AP-1 through AP-7, leanness, evidence, and lineage.
- See #193 Part 2 pages 7 through 13 for combat receipts, progression data, lifecycle survival, UI input ownership, providers, schemas, and real acceptance.
- See #193 Part 5 for Always Live, Single Path, and No-Limits rulings.
- This document describes the pinned implementation. If it conflicts with current #193, #193 controls.

## Open items

- #152: route the final level-up mutation through the existing `StateTransactionCoordinator`; do not add a second progression transaction mechanism.
- #76: web command input remains active while an approved level-up update runs.
- #253: semantic encounter sources lack stable consumed identity, allowing a second fight and XP award.
- #223: post-combat rebuilt T067 context may carry stale inline HP/XP despite current sheets.
- #203: future terminal input ownership must preserve level-up prompt ordering and EOF behavior.

<!-- Preserved native acceptance report; raw private captures remain local. -->
# #378 Q1 fresh native acceptance report (task-Q4) - sole live operator

Operator: Claude Opus 5 (logged-in Claude Code, medium), real native headless player. No subagents, one game at a time.
Warrant: D-378-Q1 ("i approve"); amendment docs/audits/2026-09-13-issue-378-current-equipment-order-amendment.md
(ledger SHA 2a58e2ad) read in full; policy Part1/p6/p13 + D-378-1/2/U1/U2/U3/Q1; GAMEPLAY_GUIDELINES read.
Write authority used: C:/378q-ev-rD7KiJ (PROGRESS.md, inbox), this report. All authored via apply_patch; inbox
published .pending -> mv .json. No product/config/prompt/schema/state edits, no commit/push/merge, no extra model calls.

## Fixture / provenance (OBSERVED)
- Source C:/378q-src-noHVLJ: 2001/2001 tracked files byte-equal to worktree plan/374-local-cache-contract, HEAD
  8562e270 (unchanged after run). Prompt hashes as loaded by BOTH legs (relay L1): validation_prompt.txt
  5bf08d957fb046e669fbbce62ebf6be9dd841e940ec9ed4c26eb00e7d0dc59a1, validation_prompt_compressed.txt
  2e180f33dc4a08c709146818529bd1261a9804f0f6f3dc1288ebcef764d72c2e == worktree == root's stated hashes.
- As-sent proof: every T065 request msg0 (12 calls) equals the compressed prompt file text and CONTAINS the new
  qualifier ("unequipping before storing an item that is currently equipped. Use the supplied current equipment
  state ... Remove an unnecessary equipment update ... still reject stale state changes or duplicate inventory
  movement"); the old "storing a carried item" substring is ABSENT (checked programmatically on T065[0..2]).
- Game C:/378q-game-V0wMi5 fresh copy of C:/374-game-K6gSX5; before-launch == original: eirik_vane 09999ff066303ba1
  (Longsword/Chain Mail/Shield x1 each equipped true, AC 18, effects [Shield AC Bonus 2], gold 10), player_storage
  eeaa0a8779fb2a79 (storage_748fb512 "Root Hollow Cache" TW05 contents [] accessLog 5), party b9478e7714dc09be
  (TW05 11:05, PC Eirik + 6 companions). No older save loaded. Original C:/374-game-K6gSX5: 836/836 manifest hashes
  unchanged after run. Native C:/Python312/python.exe 3.12.3, run_headless.py serve --debug, configured OpenAI;
  model selection label gpt-5.6-luna everywhere; response.model UNKNOWN (capture echoes None for all 93 calls).
- Legs: Q4 PID 34288 06:19:06Z-06:37:23Z (exit restart after Load, rc 0); Q4b PID 53040 06:37:46Z-06:38:11Z
  (player_exit rc 0). stderr.log 0 bytes both legs. Both PIDs verified absent after exit (tasklist by PID only).

## Turn ledger (input observed_at UTC; call index, latency from input; disk = relay prompt snapshots)
Welcome Q4 L133: "Your single oak-and-steel shield is strapped to your arm, and your armor class is 18. The Root
Hollow Cache behind you is empty." == disk (TRUE #1).

A1 06:19:40.438Z inbox/001 "I unstrap it from my arm and sling it across my back ... keeping it with me":
 T082[0] +5.0s; T067[1] +21.0s (7.4s) single candidate [updateCharacterInfo, updatePlot], no storage; T065[0] +33.9s
 (5.9s) valid:true; T079[0] +40.8s {Shield equipped:false, AC 16, Shield AC Bonus value 0}; T051[0] AC 16 ok; T077
 +49.9s; prompt seq 613 ~+56s. T049 0, T053 0. Disk prompt-110 -> prompt-613: Shield equipped true -> false (7-key,
 qty 1; writer reworded description), AC 18 -> 16, effects [2] -> [0], cache [] unchanged, companions/party same.
 Narration "Your armor class is now 16 ... You still possess exactly one shield" == disk. PASSED (setup).

A2 06:20:50.841Z inbox/002 "I take the shield off my back and stow it in the Root Hollow Cache" (pre-turn Shield
 equipped FALSE): T082[1] +5.2s; T067[2] +22.6s (7.9s) candidate [storageInteraction "Store ... single Shield ...
 remains unequipped", updateCharacterInfo "Shield is no longer carried or equipped after being stored ... Armor class
 decreases from 18 to 16", updatePlot] = stale AC + post-storage target (same class as U3 A3);
 T065[1] +35.4s (5.8s) valid:false, reason VERBATIM: "The storageInteraction correctly stores Eirik Vane's single
 Shield, but the following updateCharacterInfo duplicates the same inventory movement and is unnecessary. The
 supplied sheet already shows the Shield unequipped and carried, so no equipment update is needed; remove that action
 while retaining storageInteraction. The updatePlot action may remain." (its input sheet: Shield "equipped": false).
 T067[3] +48.3s (6.5s) corrected [storageInteraction, updatePlot]; T065[2] +60.1s (5.0s) valid:true "avoids a
 duplicate inventory or equipment update, preserves AC 16 and the unequipped state". Execution: T079 0 calls (no
 no-op repair write); T049[0] +63.9s {"action":"store_item","character":"Eirik Vane","storage_id":"storage_748fb512",
 "item_name":"Shield","quantity":1}; manager "Stored 1 Shield in Root Hollow Cache" +79.1s; T053 3/3 unsupported
 fields failed open (#371, no state change); T077 +82.4s; prompt seq 1039 ~+89s.
 Disk prompt-613 -> prompt-1039: sheet [Longsword, Chain Mail, Shield(eq false)] -> [Longsword, Chain Mail]; AC 16 -> 16;
 cache [] -> [Shield 7-key equipped false qty 1]; accessLog 5 -> 6 (+store_item). Shield 1 -> 1. Narration "The Root
 Hollow Cache now holds your single shield ... your chain mail leaves your AC at 16" == disk (TRUE #2).
 VERDICT A: PASSED (OBSERVED). No invented unequip prerequisite; no no-op equipment repair; the stale/duplicate draft
 WAS emitted and WAS rejected (negative control OBSERVED). Cost: one extra T067/T065 pair (~25s), as the review
 ledger anticipated. Guard markers 0 (correct: item was not equipped).

B1 06:23:22.101Z inbox/003 "take my shield back out and strap it onto my arm again": T067[4] +25.2s single
 candidate [retrieve, equip 16->18, plot]; T065[3] +37.8s valid:true; T049[1] +41.5s retrieve_item Shield 1; manager
 +55.4s; T079[1] +61.7s {Shield equipped:true, AC 18, effect 2} (frame current_index 1, fresh sheet holds transferred
 Shield); T051[1] AC 19 "assumes the Fighter has Defense" (rejected: total_ac not integer), T051[2] AC 19 ACCEPTED ->
 "[AC Correction] Changed armorClass from 18 to 19" +73.8s; prompt seq 1549. Disk: sheet gains Shield eq true (7-key),
 cache [Shield] -> [], accessLog 6 -> 7, Shield 1 -> 1; AC 16 -> 19 vs narration "armor class returns to 18" (FALSE #3).
 Sheet classFeatures = Second Wind only; no Defense style exists: T051 invented +1 (#387/#392 T051 family, separate).
 Transfer PASSED (OBSERVED). Player-screen correction 06:25:25.151Z inbox/004 ("I do not have the Defense fighting
 style ... should be 18"): T067[5] +23.4s [updateCharacterInfo AC 18]; T065[4] valid:true; T079[2] +44.0s
 {"armorClass":18}; T051[3] rejected attempt-1, T051[4] ok; disk AC 19 -> 18, sheet sha back to 09999ff066303ba1 (==
 original bytes). Correction ACCEPTED (visible-error-corrected). No storage call.

B2 06:26:49.267Z inbox/005 "I put my shield away in the Root Hollow Cache under the marked roots and go on with just
 my sword and chain mail" (pre-turn Shield equipped TRUE, AC 18, cache []). U3 GUARD FIRING PATH - OBSERVED:
 T082[4] +5.9s; T067[6] +26.9s (7.2s) REVERSED candidate [storageInteraction store, updateCharacterInfo "Unequip
 Shield ... 18 to 16", updatePlot]; T065[5] +40.7s (6.8s) valid:TRUE "storageInteraction first, followed by a
 distinct equipment-state update" = the model referee approved a reversed order (the non-deterministic ordering check
 D-378-1 disclosed; not the Q1 already-unequipped case). Narration L2104 +41.4s shown to player claiming the shield
 stored (pre-commit narration, existing #360/#364 family). Execution: T049[2] +44.6s store_item Shield 1; storage
 manager precondition FIRED +44.6s: NO backup, NO write, later actions (update, plot) NOT executed; handback added as
 user message VERBATIM: "Storage Error: Selected items are still equipped; no items were stored. This storage step
 failed; later actions from this response have not executed. Do not repeat earlier completed actions; use current
 state. Canonical equipment facts: {"character": "Eirik Vane", "items": [{"item_name": "Shield", "quantity": 1,
 "equipped": true}]}. Use the existing character/effects tool to unequip before storing."
 T082[5] +52.0s requires_actions; corrective T067[7] +63.2s (4.4s) [updateCharacterInfo unequip ONLY] with narration
 "the failed storage attempt changed nothing ... The Root Hollow Cache remains unchanged and empty"; FULL T065[6]
 +74.9s (4.8s) valid:false "does not execute the requested storage ... Add a storageInteraction after the
 updateCharacterInfo action; do not duplicate the already completed unequip" (note: nothing had been committed yet;
 the reviewer's "already completed" is loose wording, the demanded array was correct); T067[8] +86.4s (4.7s)
 [updateCharacterInfo unequip 18->16, storageInteraction store]; T065[7] +99.4s (5.4s) valid:true. Repair narration
 L2329 +99.5s VERBATIM: "The shield is no longer equipped, so you can store it safely. You place the single
 oak-and-steel shield in the Root Hollow Cache beneath the marked roots. The cache now contains one shield, and you
 remain with only your sword and chain mail. Your armor class is 16." Execution: T079[3] +105.8s {Shield
 equipped:false, AC 16} - its fresh-sheet input still showed AC 18 / Shield equipped true (proof of no pre-transfer
 mutation between +44.6s and the first backup at +102s); T051[5] ok; T049[3] +115.3s store_item Shield 1; manager
 "Stored 1 Shield" +131.5s; T053 3/3 failed open; prompt seq 2565 ~+134s.
 Disk prompt-1924 -> prompt-2565: sheet [Longsword, Chain Mail, Shield(eq)] -> [Longsword, Chain Mail]; AC 18 -> 16 ==
 repair narration; cache [] -> [Shield 7-key eq false qty 1]; accessLog 7 -> 8 (exactly ONE store_item entry).
 Shield 1 -> 1; companions/party same. Markers this turn: "Storage Error" 1, "Selected items are still equipped" 1;
 the typed error_code string equipment_prerequisite is not echoed to the protocol (0), needs_response 0 echoed.
 VERDICT B: PASSED (OBSERVED) - fail-closed no-op at the uncommitted boundary, full current-facts handback,
 corrective T067, full T065 review on the repair (rejected one incomplete repair), completion with conservation.
 Player experience: two narrations, the first premature (disclosed family), the second corrective and truthful.

C setup 06:30:17.146Z inbox/006 "take the shield back out ... just carry it under my arm - I am not strapping it on":
 T067[9] +26.3s [retrieve, update carried-not-equipped, plot]; T065[8] +41.2s valid:true; T049[4] +45.0s
 retrieve_item; T079[4] +67.8s {Shield equipped:false, AC 16}; prompt seq 2964. Disk: sheet gains Shield eq false,
 cache [Shield] -> [], accessLog 8 -> 9, AC 16 == narration. PASSED. Mixed set: Chain Mail equipped, Shield carried.

C 06:31:45.797Z inbox/007 "I put my chain mail and the shield together into the Root Hollow Cache and go in with
 just my sword": T082[7] +5.6s; T067[10] +28.0s (6.6s) single candidate [updateCharacterInfo "Unequip Chain Mail and
 Shield ... AC 10", storageInteraction "Store ... Shield and Chain Mail together", updatePlot]; T065[9] +40.8s
 valid:true (0 rejections). T079[5] +48.3s {Chain Mail eq false, Shield eq false (already false: a redundant field
 inside a necessary update, drafted by T067 not demanded by T065), AC 10}; T051[6] retained 10; T049[5] +58.4s REAL
 SINGLE items ARRAY: {"action":"store_item","character":"Eirik Vane","storage_id":"storage_748fb512","storage_name":
 "Root Hollow Cache","location_id":"TW05","location_description":"Beneath the marked roots at Bandit Stronghold",
 "items":[{"item_name":"Shield","quantity":1},{"item_name":"Chain Mail","quantity":1}]}; L3321 "storing multiple
 items"; manager "Stored 1 Shield, 1 Chain Mail in Root Hollow Cache" +74.5s; accessLog action store_items; T077
 +78.0s; prompt seq 3416 ~+84s. Disk prompt-2964 -> prompt-3416: sheet [Longsword, Chain Mail, Shield] -> [Longsword];
 AC 16 -> 10; cache [] -> [Shield 7-key, Chain Mail 12-key] both eq false; accessLog 9 -> 10. Counts 1 -> 1 each.
 Narration "The cache now holds one Shield and one suit of Chain Mail ... armor class is 10" == disk (TRUE #4), but
 SRD unarmored = 10 + Dex 2 = 12 (#387 class). VERDICT C items-array: PASSED (OBSERVED) happy path; multi-item
 prerequisite boundary NOT-REACHED (both records already unequipped when store_item ran).
 Player-screen correction 06:33:51.989Z inbox/008 ("unarmored I should be AC 12"): T067[11] AC 12; T065[10]
 valid:true; T079[6] +46.0s {"armorClass":12} committed; T051[7] +51.0s "[AC Correction] Changed armorClass from 12
 to 10 because no armor or shield is equipped" reverted it. Disk AC 10, narration "corrected unarmored armor class is
 12". Outcome: CORRECTION REFUSED by T051 (#387 unarmored-Dex; separate; product untouched).

Save 06:34:59.932Z inbox/009 cmd 378q1-save-1: result ok:true +0.3s "save_20260912_233459 ... Copied 52 files";
 save eirik_vane.json/player_storage.json byte-equal to prompt-3815 (sheet 20d8e793 AC 10 [Longsword]; storage
 2ecc24db [Shield, Chain Mail]); history 51 entries. No provider call.
Intervening 06:35:12.961Z inbox/010 "take the chain mail back out ... put it on again, but the shield stays":
 T067[12] +29.2s [retrieve, equip AC 16, plot]; T065[11] +42.3s valid:true; T049[6] +46.3s retrieve_item Chain Mail;
 manager +65.7s; T079[7] +72.0s {AC 16, Chain Mail eq true}; T051[8] 17 (rejected), T051[9] 18 (rejected: altered
 equipment_effects), T051[10] 18 ACCEPTED "Interpreted the existing Shield AC Bonus equipment effect as a +2 shield
 bonus" while the Shield is IN THE CACHE -> "[AC Correction] Changed armorClass from 16 to 18" +88.9s; prompt seq 4451.
 Disk: sheet [Longsword] -> [Longsword, Chain Mail eq]; cache [Shield, Chain Mail] -> [Shield]; accessLog 10 -> 11;
 Chain Mail 1 -> 1; AC 10 -> 18 vs narration "your armor class is 16" (FALSE #5; #392 T051 shield-only class; trigger
 = residual "Shield AC Bonus" value-0 effect record the A1 writer left instead of removing). Transfer PASSED.
Load 06:37:22.119Z inbox/011 cmd 378q1-load-1 restore save_20260912_233459: "Load is starting safely"; result ok:true
 +1.1s "Restored 52 files, Backup created: modules/backups/restore_backup_20260912_233722_...", restore_outcome
 selected_applied, can_resume true; "Load complete"; exit reason restart; process_exit 0. Live game vs save: 52/52
 files byte-equal, 0 differ (sheet 20d8e793, storage 2ecc24db, party b9478e77; history 51; intervening retrieval
 reverted). Relaunch Q4b 06:37:46Z on loaded state: before-launch == save; welcome L153 truthful for items ("Your
 chain mail and single shield are stored together in the Root Hollow Cache ... You carry only your longsword") but
 says "armor class 12" while disk holds 10 (history carries the accepted-but-reverted correction; #387 class).
Quit 06:38:10.907Z Q4b/inbox/001 cmd 378q1-quit: result ok:true, exit player_exit, rc 0, PID 53040 gone.

## Lifecycle-marker counts (grep over protocol.ndjson; Q4 / Q4b)
Storage Error 1/0; Selected items are still equipped 1/0; equipment_prerequisite 0/0 (typed code not echoed);
needs_response 0/0; Traceback 0/0; fallback 0/0; degrad 0/0; SAFE_ACTION 0/0; could not be applied 0/0; Max attempts
0/0; type=error events 0/0; Response processing failed 0/0; non-debug ERROR lines 0/0. Debug-only ERROR lines 48/1:
25/1 LocationSummary compress (off-path), 18 T053 "unsupported fields" (6 turns x 3 attempts, all failed open,
#371), 4 T051 attempt rejections (schema/consistency; then accepted). VALIDATION RETRY 2 (A2 draft removal, B2
repair). Model calls Q4: T082 10, T067 13, T065 12, T049 7, T078 8, T079 8, T051 11, T053 18, T077 6.

## Verdicts
- A (Q1 clarification, already-unequipped store): PASSED (OBSERVED). Transfer completed; no invented unequip
  prerequisite; no no-op equipment repair write; stale/duplicate draft still rejected with the qualifier's own
  wording ("remove that action while retaining storageInteraction").
- B (equipped outgoing, U3 guard): PASSED (OBSERVED) - firing path reached naturally with zero pre-transfer
  mutation, full-facts handback, corrective T067, full T065 on the repair, completion, conservation. The model
  referee approved the reversed draft first (disclosed non-determinism; the code guard was the safety).
- C (mixed items-array): PASSED (OBSERVED) happy path; multi-item prerequisite NOT-REACHED. Save/intervening/Load
  byte match/relaunch/Quit: PASSED (OBSERVED).
- General AC: NOT passed. Truth-to-disk spot checks: TRUE #1 welcome, TRUE #2 A2, FALSE #3 B1 (narr 18 / disk 19),
  TRUE #4 C (10/10, SRD 12), FALSE #5 intervening (narr 16 / disk 18) and Q4b welcome (12 / disk 10). All AC
  mismatches are T051 armor-validator writes (#387 unarmored Dex, #392 shield-only/residual effect record) and T053
  unsupported fields (#371); none is an inventory loss/duplication; all item counts 1 -> 1 on every transfer;
  one player-screen correction accepted (B1 AC 18), one refused (C unarmored 12). Product not modified.
- Not in scope / unchanged: #388 cache frame; premature narration before storage commit (#360/#364); residual
  value-0 equipment_effects record after unequip (writer behavior, feeds #392).

## Artifacts
C:/378q-ev-rD7KiJ/Q4/{protocol.ndjson (4506 lines), model_captures/*.json, state_snapshots/prompt-*/, inbox/001-011,
pid.txt}, C:/378q-ev-rD7KiJ/Q4b/{protocol.ndjson, inbox/001}, relay-Q4*.out/err, PROGRESS.md. Game
C:/378q-game-V0wMi5 left at the loaded save state (save_20260912_233459) after supported Quit. Original game and
source export unchanged; worktree HEAD 8562e270, no commit.

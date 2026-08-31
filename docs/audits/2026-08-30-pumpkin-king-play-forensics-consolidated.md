# Pumpkin King Alpha Play Forensics - CONSOLIDATED (2026-08-30)

STATUS: Authoritative record. Supersedes the raw /mnt/c/pkev/BUG_LEDGER.md claims
(PK-001..PK-042). Produced by codex-wsl as Part 1 (R7) of the owner-approved replay
plan (docs/audits/2026-08-30-replay-test-plan.md), under the same classification key
and evidence rules as the Thornwood forensics
(docs/audits/2026-08-30-thornwood-play-forensics-consolidated.md).
Full report embedded verbatim below.

Original location: /mnt/c/pkev/PK_PLAY_FORENSICS_REPORT.md
SHA-256: 39818e904918abe0904f321b03b794cc5ba2a220b95e711eb7bb301f4553aea3

Verdict counts: 24 MECHANIC-DEFECT, 8 PLAYER-PLAY, 8 DESIGN-WORKING,
1 UNTESTED-CLAIM (PK-023), 1 REPEAT-INDUCED (PK-009).

Highlights:
- PK-016 = POSITIVE CONTROL: the one time the player corrected the DM (wrong Cure
  Wounds dice), the correction was accepted and committed correctly. The player-screen
  correction contract worked when used.
- PK-023 (level-up "broken" at 300/300) = UNTESTED-CLAIM: Rowan's sheet reads 100/300,
  and no retained player input ever asked to level. PP005/PP007 auto-emission remains
  an owner design question, observed (not fixed) in the Part 2 replay.
- PK-024 (module can't complete) = PLAYER-PLAY: the run reached the finale with
  PP001-PP004 still open, then backtracked - a route choice, not structural proof.
- PK-026 (boss downscaled) = DESIGN-WORKING/design-choice: adaptive scaling saved a
  level-1 party in level-3 content; whether authored bosses should scale differently
  is an owner ruling, not a malfunction.
- PK-025 is the notable counter-example: the tester DID attempt an in-world correction
  (missing authored NPCs at C03) and it failed to restore the authored scene - a real
  defect in the correction path for authored content.

---
# Pumpkin King Alpha Play Forensics

Date: 2026-08-30

Scope: read-only review of PK-001 through PK-042 against the raw Pumpkin King
protocol streams, conversation histories, encounter records, captures, and durable
state under `/mnt/c/pkev` and `/mnt/c/pk004f3`. GitHub issue #193 supplied the
evidence rules. `BUG_LEDGER.md` was treated as a list of claims, never as proof.

## Executive verdict

The Pumpkin King run exposed real engine defects, but the ledger overstates the
systemic progression and balance conclusions. Rowan's current authoritative sheet is
level 1 at 100/300 XP, not 300/300, and none of the retained player inputs asks to
level up. The run also reached the finale while PP001 through PP004 were still open,
then backtracked. That play path cannot prove that the level-up interaction is broken
or that normal campaign completion is structurally impossible.

Deaths, lethal encounters, retreat choices, and Load are outcomes or player choices.
They become defects only where the surrounding mechanic malfunctioned: an unconscious
PC received an ordinary action prompt, Load was intercepted, an accepted retreat did
not close combat, or an accepted restore stopped progressing. Visible DM mistakes that
the tester did not correct are player-testing failures, not proof that the correction
contract refuses them. The one correction the player did make - Cure Wounds' dice -
was accepted and committed correctly.

## Classification key

- `MECHANIC-DEFECT`: an exercised mechanic visibly or durably malfunctioned.
- `PLAYER-PLAY`: the claimed defect follows from the tester's choice, timing, route,
  or failure to use the player-screen correction/advancement interaction.
- `DESIGN-WORKING`: validation, correction, adaptive challenge, consequences, or
  recovery behaved as intended.
- `UNTESTED-CLAIM`: the asserted mechanic was never exercised.
- `REPEAT-INDUCED`: retry, restore, repeated-action, or test-fixture residue created
  the failure.

## Finding-by-finding reclassification

| Finding | Reclassification | Raw evidence | Forensic rationale |
|---|---|---|---|
| PK-001 | MECHANIC-DEFECT | `/mnt/c/pkev/protocol-pk2.ndjson:54` | The player channel contains `Raw AI response` and the starting-location JSON. This is an exercised output-boundary leak, not play style. |
| PK-002 | PLAYER-PLAY | `/mnt/c/pkev/protocol-pk2.ndjson:107`; later Jo history at `/mnt/c/pk004f3/modules/conversation_history/conversation_history.json:144` | The first response visibly calls Jo missing and available. The tester did not correct that response. Later play explains that Jo ran back, so persistence of the contradiction was not tested. |
| PK-003 | PLAYER-PLAY | `/mnt/c/pkev/protocol-pk2.ndjson:244,247`; `/mnt/c/pkev/alpha-46f/protocol.ndjson:3344` | State says 09:20/10:20 while prose says moonlit night. It is a visible DM error, but the tester silently logged it instead of correcting it on the player screen. Correction behavior is untested. |
| PK-004 | MECHANIC-DEFECT | `/mnt/c/pkev/protocol-pk2.ndjson:284-291`; `/mnt/c/pkev/protocol-pk2-restart1.ndjson:1-14` | Legal repeated monster occurrences caused a `ValueError`, engine exit, and restart re-crash. This was a hard exercised travel defect, later fixed at `46f0269c`. |
| PK-005 | DESIGN-WORKING | `/mnt/c/pkev/alpha-46f/protocol.ndjson:161-284,361-483` | The validator initially rejected canonical trap detail, but the scoped correction loop converged on the next completed attempt without corrupting state. This is avoidable churn, not a failed player transaction. |
| PK-006 | MECHANIC-DEFECT | `/mnt/c/pkev/alpha-46f/protocol.ndjson:231,279,430,478,672,727,1056` | The diagnostic capture repeatedly raises an undefined-name warning and loses validation evidence. Gameplay continues, but the exercised capture mechanic is broken. |
| PK-007 | MECHANIC-DEFECT | `/mnt/c/pkev/alpha-46f/protocol.ndjson:98-100,193-195,248-249,392-393,447-448,627-628,689-690` | The same unchanged compression sections repeatedly fail and repeat provider work. Fail-forward preserved play, but the compression/cache mechanism itself did not converge. |
| PK-008 | DESIGN-WORKING | `/mnt/c/pkev/alpha-46f/protocol.ndjson:1793,2400` | The first answer withheld the clue, but the player's immediate plain-language follow-up produced the exact route and C05 destination. The player-screen correction/follow-up contract worked. |
| PK-009 | REPEAT-INDUCED | `/mnt/c/pkev/alpha-46f/protocol.ndjson:6666-6667` | The crash occurred at zero free disk after stale project test fixtures accumulated. Optional diagnostics should fail forward, but this campaign interruption was induced by test-fixture/disk residue rather than the travel decision. |
| PK-010 | DESIGN-WORKING | `/mnt/c/pk004f3/debug/api_captures/api_calls_master.jsonl` (C02-to-C05 exchange) | Attempt 1 emitted an incomplete encounter object; structured correction repaired it on attempt 2 and travel completed. That is the correction loop doing its job. |
| PK-011 | MECHANIC-DEFECT | `/mnt/c/pk004f3/modules/backups/restore_backup_20260829_170040_578172_b80c686478bf423494a1d66de954c8dc/modules/encounters/encounter_C05-E1.json`; matching combat history | Two player-owned Sacred Flame damage results were generated and committed without a player roll request. This directly violates the exercised dice-ownership contract. |
| PK-012 | MECHANIC-DEFECT | `/mnt/c/pk004f3/debug/api_captures/api_calls_master.jsonl` (C05 collapse exchanges); corresponding history under the 11:35-12:05 C05 segment | A later listening failure was treated as the already-resolved collapse trigger and forced a second hazard sequence. The accepted ruling contradicted the durable trigger history. |
| PK-013 | PLAYER-PLAY | `/mnt/c/pk004f3/modules/conversation_history/conversation_history.json` (11:50 C05 summary) | Narration ended with an empty quoted whisper. The tester did not ask the DM to complete or correct the visibly truncated line before continuing, so correction refusal was not tested. |
| PK-014 | MECHANIC-DEFECT | `/mnt/c/pk004f3/debug/api_captures/api_calls_master.jsonl` (12:05 C05 validation); `/mnt/c/pk004f3/modules/effects_state.json` | Validation demanded removal of `restrained_trap_1` even though no such effect existed in authoritative state. This is an exercised state/validator contradiction, not prose alone. |
| PK-015 | MECHANIC-DEFECT | `/mnt/c/pk004f3/modules/conversation_history/conversation_history.json` (13:00 travel); `/mnt/c/pk004f3/party_tracker.json` and its saved lineage | `Harvest Crossroads` was transformed into D03 `Harvest Warden's Path` and committed. The mechanic mutated to an unchosen destination rather than asking for clarification. |
| PK-016 | DESIGN-WORKING | `/mnt/c/pk004f3/modules/The_Pumpkin_Kings_Curse/saved_games/save_20260829_170320/modules/conversation_history/combat_conversation_history.json:16`; D03-E1 encounter in the matching restore backup | The game requested 2d8, the player immediately corrected it to 1d8+3 and supplied 4, and authoritative healing became 7. This is the mandated player-screen correction path succeeding. |
| PK-017 | MECHANIC-DEFECT | D03-E1 encounter under `/mnt/c/pk004f3/modules/backups/restore_backup_20260829_170040_578172_b80c686478bf423494a1d66de954c8dc/modules/encounters/` | Rowan at 0 HP/unconscious with a living hostile was given an ordinary combat prompt. Death is an outcome; the unusable down-state prompt is the defect. |
| PK-018 | MECHANIC-DEFECT | Native D03-E1 player stream retained in `/mnt/c/pk004f3/modules/logs/headless_raw.log`; D03-E1 saved combat state | The visible recovery instruction said `Load`, but ordinary `Load` was intercepted and returned the same blocked prompt while out-of-band save listing worked. The named control was not executable through the active interface. |
| PK-019 | MECHANIC-DEFECT | `/mnt/c/pk004f3/modules/logs/headless_raw.log` (10:10 D03-to-D04 departure; `T015 exhausted retries`) | A nonauthoritative departure summary exhausted schema attempts and terminated the engine. The player workflow was abandoned rather than reissued or returned recoverably. |
| PK-020 | MECHANIC-DEFECT | `/mnt/c/pk004f3/modules/The_Pumpkin_Kings_Curse/saved_games/save_20260829_175539/modules/encounters/encounter_G01-E1.json`; G01 combat log | Narration requested player initiative, but the encounter stored Rowan initiative 2 without any pending player request. The exercised player-die ownership contract failed. |
| PK-021 | PLAYER-PLAY | G01 encounter and combat log under `/mnt/c/pk004f3/combat_logs/G01-E1/`; raw completion construction in `/mnt/c/pk004f3/modules/logs/headless_raw.log:37133-37220` | Authoritative state has one wraith while narration says two. This was a visible DM error and the tester never corrected it, so the player correction contract was not exercised. |
| PK-022 | DESIGN-WORKING | `/mnt/c/pk004f3/modules/The_Pumpkin_Kings_Curse/saved_games/save_20260829_181932/modules/conversation_history/conversation_history.json:29-30`; subsequent completion in module plot lineage | The first throne narration omitted the plot action, but the player's natural next question caused PP007 to commit. Ordinary follow-up healed the omission without state editing. |
| PK-023 | UNTESTED-CLAIM | `/mnt/c/pk004f3/characters/rowan_ash.json`; all retained user messages scanned from 68 conversation-history files | Rowan is level 1 at 100/300, not 300/300. No retained player input asks to level up. Whether PP005/PP007 auto-emission should occur is a separate owner design question; the actual advancement interaction was never tried. |
| PK-024 | PLAYER-PLAY | `/mnt/c/pk004f3/modules/The_Pumpkin_Kings_Curse/module_plot.json`; `/mnt/c/pk004f3/modules/conversation_history/conversation_history.json:12` | The player reached the finale with PP001-PP004 still open, then backtracked. Incompleteness after bypassing four arcs is the played route, not proof that a fully played module cannot complete. |
| PK-025 | MECHANIC-DEFECT | Canonical C03 contract in `/mnt/c/pk004f3/modules/The_Pumpkin_Kings_Curse/areas/CMS001.json`; C03 arrival/search exchanges in the retained histories | The location requires Grella, Tom, and Morwenna on arrival. Arrival omitted them, and direct name-calling/search still returned no NPC. The tester did attempt an in-world correction and it did not restore the authored scene. |
| PK-026 | DESIGN-WORKING | H01 encounter in `/mnt/c/pk004f3/modules/The_Pumpkin_Kings_Curse/saved_games/save_20260829_181932/modules/encounters/encounter_H01-E1.json`; H01 combat log; Rowan level-1 sheet | The encounter was materially scaled down for a level-1 party that reached level-3 content. Adaptive scaling prevented an automatic wipe. Whether authored bosses should scale differently is a design choice, not a proven malfunction. |
| PK-027 | MECHANIC-DEFECT | Native C03 root-door player stream in `/mnt/c/pk004f3/modules/logs/headless_raw.log` (attempts 1 through at least 394) | Hundreds of completed continuations hot-spun without narration or prompt until Quit superseded the workflow. This is exercised liveness failure. |
| PK-028 | MECHANIC-DEFECT | C01/C03 transition histories and durable locations in `/mnt/c/pk004f3/modules/conversation_history/conversation_history.json` | From authoritative C01, an outward travel command reused C03 context and committed a backward move to C03. The immediate destination was not preserved. |
| PK-029 | DESIGN-WORKING | `/mnt/c/pk004f3/modules/conversation_history/conversation_history.json:144` | Jo explicitly says he escaped and ran back; the location summary retains that Elric remains missing. Once the whole exchange is read, past disappearance plus present witness is reconciled rather than contradictory. |
| PK-030 | DESIGN-WORKING | A05-E1/A05-E2 encounters in `/mnt/c/pk004f3/modules/backups/restore_backup_20260829_200058_264946_919d0b82cb8f48dcbc7f853da9ebfa5b/modules/encounters/`; A05 combat logs | Two failed rite stages produced two dangerous consequences. The tester immediately repeated the depleted challenge and later loaded after death. Lethality and reload are game outcomes; no duplicate event ID or arithmetic corruption is proven. |
| PK-031 | PLAYER-PLAY | B04 exchange in the retained conversation/capture lineage; `/mnt/c/pk004f3/modules/logs/headless_raw.log` | The narration explicitly said the trail went beyond mapped paths into a new region, and the player chose to follow it. New-module generation was the declared consequence; validation then failed closed with no mutation. A different in-module route remained available. |
| PK-032 | PLAYER-PLAY | A01-to-D04 transition in retained conversation history; authoritative D04 party state | The narration says the party leaves Petitioner's Rest while state correctly arrives there. This is a visible prose error that the tester did not correct through the player screen. |
| PK-033 | PLAYER-PLAY | C02-E1 encounter under `/mnt/c/pk004f3/modules/backups/restore_backup_20260829_205642_273761_259c780ce4df496b954a54d4bd80b9ec/modules/encounters/` and its combat history | The supplied total 10 missed AC 11, but the game requested damage. Instead of correcting the DM, the tester supplied 16 damage. That cannot establish correction refusal; the malformed continuation is partly induced by the player's compliance with a visibly impossible request. |
| PK-034 | MECHANIC-DEFECT | Same C02-E1 encounter and combat history | The player declared retreat twice and accepted narration said both sides disengaged, yet combat advanced to round 6 and remained active. The semantic outcome and authoritative encounter completion diverged. |
| PK-035 | MECHANIC-DEFECT | Native restore operation `pk-alpha-restore-4` in `/mnt/c/pk004f3/modules/logs/headless_raw.log`; C02-E1 durable state | Restore was accepted-deferred but produced no result or prompt for more than five minutes and made no file progress. The supported recovery operation stalled. |
| PK-036 | MECHANIC-DEFECT | D12-E1 encounter under `/mnt/c/pk004f3/modules/backups/restore_backup_20260829_212249_399796_ddb79c3bce074d07950a50fd047be37c/modules/encounters/`; player stream | Rowan at 0 HP froze the entire fight despite a living companion. Death itself is valid; suppressing ally turns, rescue, and death-save continuation is not. |
| PK-037 | MECHANIC-DEFECT | Accepted Mayor response in `/mnt/c/pk004f3/modules/conversation_history/conversation_history.json`; capture tail timestamp 22:08:17; native process evidence in the alpha record | A completed accepted response existed on disk, but the player got neither delivery nor a new prompt while the process had no provider work. The delivery/continuation workflow stalled locally. |
| PK-038 | MECHANIC-DEFECT | D14-to-D13 player stream in `/mnt/c/pk004f3/modules/logs/headless_raw.log` | Recovery succeeded, but player narration exposed `provider connection` and `ProviderCallError`. Technical transport details crossed the player-output boundary. |
| PK-039 | MECHANIC-DEFECT | `/mnt/c/pkev/alpha-46f/protocol.ndjson:218-221` in the B02-to-B01 continuation segment; matching history/capture absence | The UI advertised a ready prompt, then echoed two valid inputs without recording or processing either. Actionable readiness and input consumption disagreed. |
| PK-040 | MECHANIC-DEFECT | `/mnt/c/pk004f3/modules/conversation_history/pending_location_transition.json` in the captured alpha lineage; B01 restart/player stream | A retained `blocked_conflict` transition exposed ordinary ready prompts that could not consume any of three inputs, even after restart. Recovery state and player control were inconsistent. |
| PK-041 | MECHANIC-DEFECT | C01-to-B01 accepted transition in retained histories; party/module state after the turn | A canonical in-module return activated fabricated `The_Tanglewood_Verge`/A01 state with null plot authority. This is an exercised identity/mutation failure, not merely narration. |
| PK-042 | MECHANIC-DEFECT | Next-turn native traceback in `/mnt/c/pk004f3/modules/logs/headless_raw.log` (`main.py:8009`, null `plot_data_for_note`) | The engine advertised a prompt in invalid module state and then dereferenced a null plot and exited. PK-041 caused the state, but the missing fail-forward guard is independently exercised. |

## Cross-cutting conclusions

### Progression and campaign route

PK-023 is not evidence that level-up mechanics fail. The current sheet reads 100/300,
and the retained user corpus contains no advancement request. The first run also reached
PP007 while PP001 through PP004 remained active. PK-024 is therefore a route/play result,
not proof that a full, normally progressed Pumpkin King lineage cannot complete. The
fresh replay must separately observe both owner-open questions: player-requested level-up
at threshold and plot-authored `levelUp` emission after PP005/PP007.

### Lethality and reloads

The A05 repeated rite and level-1 H01 finale do not prove broken balance. A failed rite
may create danger, companions may die, and a player may reload. The valid defects are
the mechanics around those outcomes: ordinary prompts at 0 HP, frozen living allies,
intercepted Load, stalled Restore, or retreat narration that never commits escape.

### Player correction discipline

PK-016 is the positive control: the player said the requested healing dice were wrong,
gave the correct roll, and the game committed 7 healing. By contrast, the tester did not
correct the time-of-day prose, phantom second wraith, incomplete whisper, reversed arrival
sentence, or missed-attack damage request. Those rows cannot be used as evidence that the
player-screen correction contract refuses correction. The replay must correct visible DM
errors immediately and record both the original error and the response.

### Surviving defect surface

The strongest exercised defects are narrow and concrete: travel/reconciliation crashes,
wrong destination commits, automatic player dice, validator/state contradictions,
post-response and continuation liveness failures, down-state/recovery gaps, partial
transition conflicts, input-readiness mismatches, and invalid module identity mutation.
These findings survive without relying on claims that combat should be nonlethal or that
the player should receive progression without actually following the progression route.

## Final disposition

Counts across PK-001 through PK-042:

- MECHANIC-DEFECT: 24
- PLAYER-PLAY: 8
- DESIGN-WORKING: 8
- UNTESTED-CLAIM: 1
- REPEAT-INDUCED: 1

Part 2 must be treated as a fresh experiment, not an attempt to reproduce the first
tester's conclusions. It will fight encounters, track XP, request advancement at the
threshold, correct visible DM mistakes on-screen, and observe - without deciding - whether
the PP005 and PP007 plot instructions automatically emit `levelUp`.

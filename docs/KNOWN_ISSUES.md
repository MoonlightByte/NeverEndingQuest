# KNOWN ISSUES - awaiting owner review (2026-08-30)

OWNER DIRECTIVE: do NOT open GitHub issues for anything in this list until the owner
has reviewed each item individually. This is the holding pen for real, transcript-cited
defects that survived the 2026-08-30 play forensics, plus new findings from the
good-play replays. Master evidence:

- docs/audits/2026-08-30-code-defects-from-alpha-forensics.md (the full 52+5 work list,
  every row cited: Thornwood Part 1 + Pumpkin King Part 2)
- docs/audits/2026-08-30-thornwood-play-forensics-consolidated.md
- docs/audits/2026-08-30-pumpkin-king-play-forensics-consolidated.md
- Replay evidence: validation_evidence/thornwood_replay/ (+ GOOD_PLAY_LEDGER.md) and
  /mnt/c/pkev/replay-r2/

## A. Defect clusters pending owner review (details + citations in the work-list doc)
1. Zero-HP / recovery seam (5 rows: TW-F01/F40, PK-017/018/036) - unconscious PC gets a
   normal prompt; typed Load intercepted; a downed PC freezes living allies. The
   DOWN-SCENE DESIGN is owner-only (deaths themselves are intended challenge; #246
   closed accordingly; the narrow mechanic seam is still real, #242 remains open).
2. Liveness / continuation stalls (7 rows: TW-F08, PK-019/027/035/037/039/040).
3. State-vs-narration divergence (10 rows: TW-F22/F27/F31/F36/F37/F39/F43 + PK-012/014).
   NOTE: the replay showed several of these are live-correctable via the player screen
   (rest/reward corrections accepted; Second Wind committed correctly this run), which
   LOWERS their severity - fix priority is an owner call.
4. Action contracts / inventory (6 rows: TW-F06/F12/F14/F15/F20 + replay storage finding
   in item C1 below).
5. Travel / module identity (7 rows: TW-F17/F29/F34, PK-015/028/041/042).
6. Roll / check adjudication + dice ownership (6 rows: TW-F09/F25/F28/F41, PK-011/020).
7. Canonical-name validation loops (3 rows: TW-F11/F38/F21).
8. Player-output boundary leaks (2 rows: PK-001/038).
9. Capture / compression plumbing (2 rows: PK-006/007).
10. Authored-content restoration (1 row: PK-025 - the one confirmed correction-path
    failure; authored NPCs missing at C03 could not be restored in-world).
11. Combat closure (1 row: PK-034 - accepted retreat narration never closes combat).
12. Repeat-induced / restore residue (5 rows: TW-F16/F23/F24/F42 + PK-009; see also C2).

## B. Items with GitHub issues ALREADY OPEN (no action needed here)
#237 #238 #239 #240 #241 #242 #243 #244 #245 #247 #248 #249 #250 #253 all map to
surviving defect rows and stay open. Closed by owner ruling 2026-08-30: #246
(survivability framing - deaths are intended challenge), #251 (advancement authority -
level-up is intentionally player-initiated; mechanic proven working live), #252
(monster special-mechanics execution - design-bearing, deferred to the owner's
post-voices refactor).

## C. NEW findings from the good-play replays (not yet in the forensic docs)
1. [Thornwood replay] Storage contract: first exchange ran 14 validation retries,
   emitted storageInteraction TWICE, hit "Invalid storage operation", yet narrated
   success. Evidence: validation_evidence/thornwood_replay/46f-r1/relay/ +
   GOOD_PLAY_LEDGER.md. (Same family as TW-F06/F20.)
2. [PK replay] After supported Load/retry at the final boss: repeated player/NPC
   death-continuity errors and duplicate-PC narration on the restored lineage.
   Evidence: /mnt/c/pkev/replay-r2/protocol.ndjson. (Same family as TW-F16 restore
   contamination - now reproduced under GOOD play, so it is not tester-induced.)
3. [Thornwood replay] Monster suffix leak (Bandit_3) appeared in narration; on-screen
   correction accepted and next DM request used the clean name. (Known T097-family
   leak; live-correctable.)
4. [Both replays] Provider 429 handling: PS's run is parked mid-campaign on persistent
   OpenAI 429s (T065/T067); stopped cleanly at the three-strikes boundary. Whether the
   engine should surface a friendlier player-facing wait/retry experience is untested.

## D. Deferred by owner ruling (post-voices refactor; do not work)
- Progression/level-up UX (auto-fire vs ask-driven is SETTLED for now: ask-driven is
  intended; screen shows XP; replay proved the flow works). Plot-authored levelUp
  instructions in module_plot.json remain unwired by design for now.
- Monster special/legendary/lair mechanics execution (ex-#252).
- Boss/encounter scaling policy (PK-026 adaptive downscale = working as designed).

## E. Deleted-branch recovery SHAs (work preserved, branches removed 2026-08-30)
Unmerged commits recoverable via reflog/SHA if ever wanted:
- fix/tw019-second-wind-retry -> a13a9630 (Second Wind retry fix; replay showed the
  feature committing correctly, so premise weakened; TW-F31 row stands as history).
- fix/survivability-feature-hp -> a496e3b4 (survivability framing invalidated).
Merged-and-deleted (content already in premerge tip 46f0269c): plan/levelup-monster-
materialization, plan/pk004-travel-reconciliation, fix/pk004-duplicate-monster-
reconciliation, fix/tw013-combat-narration-correction, fix/tw002-wizard-silent-recovery,
fix/tw005-departure-journal-failforward, fix/tw008-compaction-guard-recovery.
tw008's uncommitted worktree changes preserved at
docs/audits/2026-08-27-tw008-uncommitted-work.patch; all worktree plan docs copied into
docs/audits/.

## F. Outstanding replay work (parked, owner schedules)
- PS Thornwood: resumable at TW06, HP 12/12, XP 225/300 once 429s clear; level-up probe
  (R1) and fresh NC05 roster probes (R4) still outstanding.
- WSL PK: final-boss retry in progress lineage at Sinkhole Furrow save; final report
  pending.

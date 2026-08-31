# Code Defects Surviving the Play Forensics (2026-08-30)

Source: docs/audits/2026-08-30-thornwood-play-forensics-consolidated.md (the
authoritative finding-by-finding table with exact transcript citations). This document
is the WORK LIST: only findings that survived reclassification as MECHANIC-DEFECT (28)
or REPEAT-INDUCED (4), grouped by subsystem. Deaths, lethality, reloads, companion
agency, and validator churn were all reclassified out - they are NOT here.

SCOPE NOTE: Part 1 covers the Thornwood alpha. Part 2 (appended below) covers the
Pumpkin King ledger after its R7 forensic pass completed the same day - 24 defects +
1 repeat-induced survive there (see
docs/audits/2026-08-30-pumpkin-king-play-forensics-consolidated.md).

Evidence base for every row: relay NDJSON under
.worktrees/premerge-combat-tip-validation/validation_evidence/thornwood_alpha/ (line
citations in the consolidated doc). All against tip 46f0269c (integration/premerge-214-combat).

## 1. Zero-HP / recovery seam (2)
- TW-F01: at 0 HP the game presents an ordinary player prompt to an unconscious PC;
  no rescue/death-save scene advances. (46f-r1 protocol:5543-5544)
- TW-F40: typed `Load` at 0 HP is rejected by the incapacitated guard - Load is a
  recovery control, not a gameplay action that guard may intercept. (46f-r6-retry38)

## 2. Silent state-vs-narration divergence (7)
- TW-F31: Second Wind charge consumed (usage -> 0) with NO HP increase. Silent
  resource/HP divergence on an exercised class feature. (retry5:31831-32076)
- TW-F36: narration put Bex unconscious at 0 HP while authoritative state had her
  alive at 4 HP. (retry10:3560 vs :4316-4364)
- TW-F37: guarded short rest narrated as completed but committed neither the hour
  nor any recovery. (retry10:4772, :5028)
- TW-F39: long-rest narration (8 hours, full recovery) with no authoritative
  time/HP change. (retry39)
- TW-F27: "midday" prose against a 16:25+ authoritative clock. (retry5:19213)
- TW-F43: final arrival narrated as afternoon mist against 03:55/night state.
  (retry40 + conversation_history.json:157)
- TW-F22: Bex pronoun drift across scenes (visible continuity defect, nonblocking).

## 3. Roll / check adjudication (4)
- TW-F09: successful requested Persuasion 16 vs DC 15 accepted, then given no
  semantic consequence (scene proceeded to hostility as if failed). (r3-resume1)
- TW-F25: valid "16 on the die ... total 21" input rejected as an invalid d20 face;
  raw "16" then accepted. (retry5:16339-16401)
- TW-F28: requested d20+modifier check treated raw 11 as total 11, omitting the
  known +4. (retry5:21369, :21652)
- TW-F41: attack adjudication contradicted submitted rolls - a low total narrated as
  a hit; a natural 20 narrated with no damage. (retry38:6967-7258; retry40 NC05-E2)

## 4. Canonical-name validation loops (3)
- TW-F11: `alaric_vale` vs `Alaric Vale` - deterministic normalization and validation
  disagree, so completed calls cannot converge; recurred across runs. (r4:4590-4873)
- TW-F38: same name-normalization conflict turned the Withered Hart cleansing quest
  action into an unbounded correction loop (11+ retries, no terminal). (retry36)
- TW-F21: authored NPC (Scout Neris) absent from the canonical identity projection at
  the validation boundary, so truthful scene references validated as invalid. (retry4:4033)

## 5. Action contracts / inventory (5)
- TW-F06: accepted recruitment turn also emitted an incompatible Gold-storage action
  that failed with a visible diagnostic. (r2:1515-1541)
- TW-F12: gifted potion could not be acquired by any authoritative action - the
  demanded storage path requires prior ownership; narration claimed it was secured.
  (r4-resume1:284-416)
- TW-F14: schema-invalid item type (`quest item`) caused the companion inventory
  write to reject while narration granted carriage. (r4-resume2:300-337)
- TW-F15: purchased potion narrated as carried but committed to storage; a later
  retrieval repaired usability, not the original divergence. (r4-resume2:1801-2743)
- TW-F20: quest turn-in advanced plot but the reward/removal transaction only
  partially committed (storage_name: null failure). (retry3:439-612)

## 6. Travel (3)
- TW-F17: companion assigned to stand guard was silently present at the destination
  after travel - contradicting the immediately preceding player-owned assignment.
  (46f-r6-fresh:3378, :3608)
- TW-F29: arrival narration performed future movement beyond the committed one-beat
  destination (passed the cave despite stop-at-approach intent). (retry5:20561, :20609)
- TW-F34: travel request to the Nexus committed NC02 instead. Wrong destination
  committed. (retry8:1983, :2394-2442)

## 7. Plot / progression integrity (2)
- TW-F18: one relay completed a three-tower objective and started PP005 before its
  listed prerequisites - durable progression divergence. (46f-r6-fresh:5540-5925)
- TW-F19: bell-key handoff produced an unsatisfiable action contract - successive
  corrections alternately demanded transfer and retention. (46f-r6-fresh after :5925)

## 8. Content bootstrap / liveness (2)
- TW-F13: canonical rescue encounter (Wolf's Den) could not materialize - NPC-builder
  claimed success, then encounter creation failed on two real entries. (r4-resume1)
- TW-F08: peaceful-combat intent stalled after enrichment/NPC load; no gameplay
  output ever returned in that run (liveness failure, cause unattributed). (r3:2855-2858)

## 9. REPEAT-INDUCED (retry/restore residue - real, distinct track) (4)
- TW-F16: restore left later-scene conversational authority over earlier
  authoritative state (restored to RO01/no-companions; narration continued the later
  stronghold scene with Kira/Bex). (r4-resume2:7546-7575; r5-replay:184,401)
- TW-F24: repeating the same investigation spawned a duplicate ambush encounter
  (RO06-E1/E2) with a second XP award for the same local threat. (retry5:7610, :9041)
- TW-F23: runaway repeated T096 test loop exhausted disk ("No space left on device")
  and broke live turns. (retry3:2087; retry4:4096)
- TW-F42: NC05 roster collapsed to Malarok-only after ~40 reload/retry iterations,
  against authored context of Malarok + 2-4 bodyguards + 2-4 wolves. Classified
  retry-context residue PENDING the fresh no-retry comparison in the replay plan.
  (retry8:6186-6631 vs retry40:3016-3752; authored context retry18:749)

## Explicitly NOT defects (do not re-open without new on-screen evidence)
- Level-up "broken" (never requested in either campaign; Thornwood never reached
  threshold; PK-023 = UNTESTED-CLAIM, see replay plan).
- Finale/NC01/NC02/NC03 lethality, companion deaths, reload-to-retry (DESIGN-WORKING).
- Kira ignoring target advice (companion agency working).
- T065 four-correction travel churn (validator converged; performance observation).
- XP amounts/splits (verified arithmetic: 16x4 + 66x2 = 196/300, 3-way division correct).

## Design-bearing items requiring OWNER mechanical direction before any plan
Per standing rule (consult mechanical structure first):
1. The 0-HP down-scene (TW-F01/F40 + the deferred #246 agentic-death direction).
2. Whether plot-triggered levelUp should auto-fire vs stay conversation-initiated
   (the PK module_plot.json expectation - untested either way).
All other rows above are contained mechanical fixes with one obvious correct outcome.

---

# PART 2: Pumpkin King defects surviving the R7 forensic pass (added 2026-08-30)

Source: docs/audits/2026-08-30-pumpkin-king-play-forensics-consolidated.md (verdict
table with raw-evidence citations). 24 MECHANIC-DEFECT + 1 REPEAT-INDUCED survive out
of 42 ledger claims; 8 player-play, 8 design-working, 1 untested (PK-023) dissolve.
Grouped by subsystem; many rhyme with the Thornwood groups above.

## 1. Zero-HP / recovery seam (3) - same seam as TW-F01/F40
- PK-017: unconscious Rowan given an ordinary combat prompt with a living hostile.
- PK-018: visible recovery instruction said `Load`, but typed Load was intercepted
  and returned the same blocked prompt.
- PK-036: Rowan at 0 HP froze the entire fight despite a living companion (ally
  turns, rescue, death-save continuation all suppressed).

## 2. Player dice ownership (2)
- PK-011: two player-owned Sacred Flame damage results generated and committed with
  no player roll request.
- PK-020: encounter stored Rowan initiative 2 with no pending player request while
  narration asked the player to roll.

## 3. Travel / module identity (4)
- PK-015: `Harvest Crossroads` silently mutated to D03 `Harvest Warden's Path` and
  committed instead of asking for clarification.
- PK-028: outward travel from C01 reused C03 context and committed a backward move.
- PK-041: a canonical in-module return activated fabricated `The_Tanglewood_Verge`/A01
  state with null plot authority (identity/mutation failure).
- PK-042: next turn after PK-041 dereferenced null `plot_data_for_note`
  (main.py:8009) and exited - missing fail-forward guard, independently exercised.

## 4. Liveness / continuation (6)
- PK-019: nonauthoritative T015 departure summary exhausted schema retries and
  terminated the engine (workflow abandoned, not reissued).
- PK-027: root-door interaction hot-spun 394+ completed continuations with no
  narration or prompt until Quit.
- PK-035: accepted restore (`pk-alpha-restore-4`) produced no result/prompt for 5+
  minutes with no file progress.
- PK-037: a completed accepted response existed on disk but was never delivered and
  no new prompt appeared (local delivery stall).
- PK-039: UI advertised a ready prompt then echoed two valid inputs without
  recording or processing either.
- PK-040: retained `blocked_conflict` pending transition exposed ready prompts that
  could not consume any input, even after restart.

## 5. Validator / state contradictions (2)
- PK-012: a later listening failure was treated as the already-resolved collapse
  trigger, forcing a duplicate hazard sequence against durable trigger history.
- PK-014: validation demanded removal of `restrained_trap_1`, an effect that did not
  exist in authoritative state.

## 6. Player-output boundary leaks (2)
- PK-001: `Raw AI response` + starting-location JSON leaked into the player channel.
- PK-038: `provider connection` / `ProviderCallError` transport details leaked into
  player narration during recovery.

## 7. Capture / compression plumbing (2)
- PK-006: diagnostic capture raises an undefined-name warning repeatedly and loses
  validation evidence (game continues; capture mechanic broken).
- PK-007: identical compression sections fail repeatedly and re-run provider work
  (fail-forward held, mechanism never converges).

## 8. Authored-content restoration (1)
- PK-025: C03 arrival omitted required NPCs (Grella/Tom/Morwenna); the tester DID
  attempt in-world correction and it failed to restore the authored scene. The one
  confirmed failure of the correction path (vs PK-016, the positive control where
  a dice correction committed perfectly).

## 9. Combat closure (1)
- PK-034: retreat declared twice, narration accepted both sides disengaging, yet
  combat advanced to round 6 and stayed active (matches TW PK-034 note; overlaps the
  narrated-escape seam flagged in the death brief).

## 10. Already fixed on tip (1)
- PK-004: repeated-monster reconcile ValueError crash - FIXED at 46f0269c
  (validated); listed for lineage only.

## 11. REPEAT-INDUCED (1)
- PK-009: campaign crash at zero free disk from accumulated stale test fixtures
  (same disk-residue class as TW-F23).

## PK rows explicitly NOT defects
- PK-023 level-up (UNTESTED: sheet reads 100/300, no advancement request ever made).
- PK-024 module-incompletable (route bypassed PP001-PP004; play choice).
- PK-026 boss downscale (adaptive scaling working; authored-boss scaling policy is
  an owner design ruling).
- PK-002/003/013/021/032/033 visible DM errors never corrected by the tester
  (correction contract untested on those rows).
- PK-005/008/010/016/022/029/030/031 validation churn-then-converge, follow-up
  healing omissions, lethal consequences, and fail-closed module-boundary refusal -
  all design working.

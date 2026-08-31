# Thornwood Alpha Play Forensics - CONSOLIDATED (2026-08-30)

STATUS: Authoritative record. Supersedes the raw ALPHA_LEDGER.md claims for the
Thornwood alpha and the PK-023 progression claim. The full codex-wsl forensic report
is embedded verbatim in Part C. Companion documents:

- docs/audits/2026-08-30-code-defects-from-alpha-forensics.md (the surviving code defects)
- docs/audits/2026-08-30-replay-test-plan.md (what still needs real play testing)
- docs/GAMEPLAY_GUIDELINES_FOR_AGENT_PLAYERS.md (attach to ps/wsl for all future playthroughs)

## Part A - Why this review happened (owner course-correction)

The owner personally completed Thornwood at LEVEL 3, doing everything. The alpha
runs' "systemic" narrative (level-up broken, finale unwinnable, game too lethal) was
therefore suspect. Owner doctrine, now standing:

- Deaths of PCs/NPCs are NOT design flaws. Lethality = challenge; reloading saves is
  game-making 101.
- The player screen is the correction mechanism. Real players say "you got that
  wrong" or "Kira needs to level up." An agent that never uses it is a bad player,
  not a bug reporter.
- Per finding, the only questions are: (a) did a mechanic actually malfunction
  on-screen? (b) did the agent bypass the necessary steps / play badly? (c) did the
  repeat/reload pattern itself cause the problem?

Two independent reviews ran against the RAW transcripts (ledger prose treated as
claims, not proof): a Claude verifier pass and the codex-wsl full forensic pass.
They converged.

## Part B - Independently verified facts (Claude verifier, raw-transcript citations)

1. LEVEL-UP WAS NEVER REQUESTED, IN EITHER CAMPAIGN. Across all 534 Thornwood player
   inputs (49 run dirs, commands.ndjson) and all 254 Pumpkin King user messages
   (17 conversation backups + live history at /mnt/c/pk004f3), there is ZERO
   occurrence of a level-up request. The only "level" hits are Second Wind math
   prose. Nobody asked and got refused - the request never happened.
2. PK-023's PREMISE IS UNCONFIRMED. On-disk /mnt/c/pk004f3/characters/rowan_ash.json
   reads level 1, experience_points 100/300 - not the 300/300 the ledger claimed.
   The residual open question is whether the module_plot.json plot-triggered levelUp
   instruction (after PP005/PP007) should auto-fire; that is a content/prompt
   expectation, untested, not a proven mechanic failure.
3. FINAL THORNWOOD XP = 196/300, ARITHMETICALLY CORRECT. Awards were consistently
   divided 3 ways among Alaric, Kira, Bex (200 XP -> 66 each; 50 XP -> 16 each).
   Completed lineage: 16+16+16+16+66+66 = 196. Low XP came from bypassing
   NC01/NC02/NC03, peaceful no-XP resolutions, and ~39 finale reloads correctly
   discarding XP from failed branches.
4. THE "UNWINNABLE" FINALE WAS WON AT LEVEL 1 (retry40, PC ended 12/12 HP). NC01 and
   NC02 were ALSO won at level 1 (each with a companion death, then rolled back by
   choice). The NC05 roster is authored as a range (Malarok 1, bodyguards 2-4,
   wolves 2-4); retry8 rolled 5 enemies, retry40 effectively 1. wsl classifies the
   late roster collapse as REPEAT-INDUCED pending a fresh no-retry comparison.
5. THE PLAYER NEVER USED THE PLAYER SCREEN. All 534 inputs were pure action
   commands. Even where the ledger itself logged a visible DM error (false
   "Bex at 0 HP" narration), the agent logged the defect and continued instead of
   correcting the DM.

## Part C - Full codex-wsl forensic report (verbatim)

Original location: .worktrees/premerge-combat-tip-validation/validation_evidence/thornwood_alpha/PLAY_FORENSICS_REPORT.md
SHA-256: cb5dc824e9cc3699ed91cc3992ed526c128544f8925b6e75c7511bc3f6bcb4ce

---
# Thornwood Alpha Play Forensics

Date: 2026-08-30

Scope: read-only review of the codex-ps Thornwood alpha transcripts, the final
conversation/state, and the Pumpkin King PK-023 progression claim. This report applies
the evidence and verdict rules in GitHub issue #193. Ledger prose was treated as a claim,
not as proof. Citations below point to the actual NDJSON line (the recorded `seq` is the
same unless noted).

## Executive verdict

The broad narrative that Thornwood was mechanically unwinnable because level-up was
broken is not supported. Alaric finished at 196/300 XP, never became eligible to level,
and no player command attempted advancement. The completed lineage deliberately bypassed
NC01, NC02, and NC03, resolved several objectives without combat, and restored away XP
earned on lethal branches. The final battle was won at level 1. Those are play-history
facts, not proof of a broken level-up mechanic.

Real defects remain. They are narrower: state/narration divergence, failed action
contracts, correction-loop liveness, restore contamination, duplicate encounter creation,
incorrect roll handling, and recovery/down-state gaps. Death, lethality, tactical defeat,
and choosing to reload are not defects by themselves.

## Classification key

- `MECHANIC-DEFECT`: an exercised mechanic visibly or durably malfunctioned.
- `PLAYER-PLAY`: the result followed from the tester's choices or failure to use the
  available player correction/advancement interaction.
- `DESIGN-WORKING`: challenge, death, independent companion choice, validation, or reload
  behaved as intended.
- `UNTESTED-CLAIM`: the asserted mechanic was never exercised.
- `REPEAT-INDUCED`: retry/restore/repeated-action residue created the problem.

## Finding-by-finding reclassification

The Thornwood IDs below (`TW-F01` through `TW-F43`) correspond in order to rows 11-53 of
`ALPHA_LEDGER.md`.

| Finding | Old claim | Reclassification | Transcript evidence | Rationale |
|---|---|---|---|---|
| TW-F01 | At 0 HP combat pauses with no rescue path (#242/#246). | MECHANIC-DEFECT | `46f-r1/relay/protocol.ndjson:5543-5544` shows an ordinary player prompt at HP 0/unconscious. | Death is allowed; asking an unconscious PC for a command while no rescue/death-save scene advances is the malfunction. |
| TW-F02 | NC01 roster was unfair at level 1. | DESIGN-WORKING | `46f-r6-retry5/relay/protocol.ndjson:23781-27441` records the party defeating the encounter; the ending includes Kira's death. | The fight was lethal but winnable. A companion death does not convert a completed combat into a defect. |
| TW-F03 | Suggested healing potion was absent. | PLAYER-PLAY | `46f-r6-retry1/relay/protocol.ndjson:198` records the player negotiating for a potion rather than possessing one; later purchase/retrieval is recorded at `46f-r4-resume2/relay/protocol.ndjson:1801-2743`. | An item suggested outside authoritative state is not inventory. The tester correctly sought one in play. |
| TW-F04 | Disengage/retreat did not exit NC01. | PLAYER-PLAY | `46f-r1/relay/protocol.ndjson:4952-4955` shows the command at 3 HP: disengage/back to the cave mouth while not leaving Kira exposed; combat then continued to `:5544`. | This was a tactical repositioning with an explicit stay-with-Kira condition, not an unambiguous encounter-exit transaction. It does not prove escape mechanics failed. |
| TW-F05 | Kira ignored repeated target instructions. | DESIGN-WORKING | The instructions and subsequent independent NPC turns are in `46f-r1/relay/commands.ndjson:6` and `46f-r1/relay/protocol.ndjson` rounds 2-5. | Companions act independently. Advice is not player control, and targeting the cave fisher was a legal agentic choice. |
| TW-F06 | Bex recruitment also emitted a failing Gold storage action. | MECHANIC-DEFECT | `46f-r2/relay/protocol.ndjson:1515-1541` records the redundant storage failure; `:1631` proves the correct 10 GP to 5 GP result. | Recruitment succeeded, but the same accepted turn emitted an incompatible extra mechanical action and visible diagnostic. |
| TW-F07 | T065 required four corrections before lawful travel. | DESIGN-WORKING | `46f-r2/relay/protocol.ndjson:3306-3309` records retry 4; `:3560` delivers the correct NC01 arrival. | The validator rejected unsafe action order and converged without mutation loss. Churn is a performance observation, not a failed mechanic here. |
| TW-F08 | Peaceful-combat intent stalled. | MECHANIC-DEFECT | `46f-r3/relay/protocol.ndjson:2855-2858` stops after enrichment/NPC load and never returns gameplay output in that run. | The player workflow stopped and required process termination. The artifact does not prove provider blame, only the observed liveness failure. |
| TW-F09 | Successful Persuasion 16 versus DC 15 was not applied. | MECHANIC-DEFECT | The requested DC is at `46f-r3-resume1/relay/protocol.ndjson:491`; the accepted 16 and no-change continuation occur before the hostile resolution at `:1065`. | An exercised, successful requested check did not produce its stated semantic consequence. |
| TW-F10 | Naiad then reduced Alaric from full HP to 0. | DESIGN-WORKING | `46f-r3-resume1/relay/protocol.ndjson:1065-1110` records the attack, unconscious state, and 0 HP. | A lethal enemy hit is combat challenge working. The ignored check is the separate defect in TW-F09. |
| TW-F11 | Canonical-name validation loops indefinitely. | MECHANIC-DEFECT | `46f-r4/relay/protocol.ndjson:4590-4873` shows retries 6-10 on `alaric_vale` versus `Alaric Vale`; recurrence is at `46f-r4-resume1/relay/protocol.ndjson:9440-9716`. | Deterministic normalization and validation disagree, so completed calls cannot converge. |
| TW-F12 | Maelo gift cannot be transferred by demanded action contract. | MECHANIC-DEFECT | `46f-r4-resume1/relay/protocol.ndjson:284-287` shows the proposed character update entering validation; `:413-416` shows the demanded storage path fail because the potion is not already owned. | Narration said the gift was secured while no authoritative inventory acquisition was possible. |
| TW-F13 | Wolf's Den cannot bootstrap rescue NPC. | MECHANIC-DEFECT | `46f-r4-resume1/relay/protocol.ndjson:2765-2768`, `:3510-3513`, and `:5035-6183` record NPC-builder success claims followed by encounter failure on two real entries. | A canonical rescue encounter could not materialize despite legitimate retries. |
| TW-F14 | Sila chest uses schema-invalid `quest item`. | MECHANIC-DEFECT | `46f-r4-resume2/relay/protocol.ndjson:300-337` narrates carriage then rejects the companion write; the plot continued afterward. | Player-visible possession and authoritative inventory diverged. |
| TW-F15 | Purchased potion was stored, not carried. | MECHANIC-DEFECT | Purchase/storage and later retrieval are at `46f-r4-resume2/relay/protocol.ndjson:1801-2743`. | The first narration falsely claimed carried possession. A later supported retrieval repaired usability but not the original divergence. |
| TW-F16 | Restore retained later stronghold scene authority. | REPEAT-INDUCED | Restore completion is at `46f-r4-resume2/relay/protocol.ndjson:7546-7575`; restored state at `46f-r5-replay/relay/protocol.ndjson:184` is RO01/no companions, while `:401` narrates the later stronghold/Kira/Bex scene. | The inconsistency was created by restoring across a later played branch while stale conversation authority survived. |
| TW-F17 | Kira teleported despite guard assignment. | MECHANIC-DEFECT | The solo guard/departure input follows `46f-r6-fresh/relay/protocol.ndjson:3378`; arrival at `:3608` places Kira with Alaric. | The delivered scene contradicted the immediately preceding player-owned assignment without a transition. |
| TW-F18 | SQ001/PP005 progression contradicted prerequisites. | MECHANIC-DEFECT | Relay action is narrated at `46f-r6-fresh/relay/protocol.ndjson:5540`; return/progression appears at `:5877-5925`. | One relay completed a three-tower objective and started PP005 before its listed prerequisites. This is durable progression divergence. |
| TW-F19 | Bell-key handoff became contradictory/impassable. | MECHANIC-DEFECT | The Kira continuity conflict begins after `46f-r6-fresh/relay/protocol.ndjson:5925`; subsequent real corrections alternately require transfer and retention in the same run. | The immediate action contract had no satisfiable accepted result. No restore was required to create it. |
| TW-F20 | Sila chest return advanced plot but failed storage/reward. | MECHANIC-DEFECT | `46f-r6-retry3/relay/protocol.ndjson:439` narrates acceptance; `:475-497` records `storage_name: null` failure; `:612` shows the resulting state. | The accepted reward/removal transaction only partially committed. |
| TW-F21 | Missing Scout Neris identity caused correction churn. | MECHANIC-DEFECT | `46f-r6-retry4/relay/protocol.ndjson:4033-4036` rejects established scene names that were absent from the supplied canonical identity projection. | Authored content was not available at the validation boundary, making truthful references invalid. |
| TW-F22 | Bex pronouns drifted. | MECHANIC-DEFECT | Contradictory pronouns occur across `46f-r6-retry3/relay/protocol.ndjson` Sila/RO01/RO04 narration and `46f-r6-retry4/relay/protocol.ndjson` combat/investigation narration. | This is a visible continuity defect, though nonblocking. |
| TW-F23 | Orphan tests exhausted disk and broke turns. | REPEAT-INDUCED | `46f-r6-retry3/relay/protocol.ndjson:2087-2088` and `46f-r6-retry4/relay/protocol.ndjson:4096-4097` terminate with `No space left on device`; the ledger's captured process/file evidence identifies the repeated T096 test loop. | The campaign failures were induced by runaway repeated test work, not by those player turns. |
| TW-F24 | North Tower immediately spawned a duplicate ambush and reward. | REPEAT-INDUCED | `46f-r6-retry5/relay/protocol.ndjson:7610` shows 32 XP while RO06-E2 is active; `:9041` shows 48 XP after E2, following the prior RO06-E1 completion. | Repeating the same investigation created E2 and another 16 XP for the same local threat. The XP arithmetic is correct for two committed combats; creating the second combat is the residue defect. |
| TW-F25 | Described raw roll plus total was rejected. | MECHANIC-DEFECT | Request/rejection/retry are at `46f-r6-retry5/relay/protocol.ndjson:16339-16401`; raw `16` then resumes. | A valid, unambiguous `16 on the die ... total 21` input was parsed as an invalid d20 face. |
| TW-F26 | Input sent before the actual prompt was delayed. | PLAYER-PLAY | `46f-r6-retry5/relay/protocol.ndjson:14120-14235` shows narration before readiness; resend after the prompt creates combat at `:14582`. | The tester violated the one-command-at-an-authoritative-prompt discipline. The game processed the correctly timed resend. |
| TW-F27 | Midday prose contradicted late-afternoon clock. | MECHANIC-DEFECT | `46f-r6-retry5/relay/protocol.ndjson:19213` says midday after a 16:25 departure; adjacent state retains the late-afternoon clock. | Player-visible narration contradicted authoritative time. |
| TW-F28 | Perception modifier omitted. | MECHANIC-DEFECT | Request at `46f-r6-retry5/relay/protocol.ndjson:21369` asks for d20 plus modifier; result at `:21652` treats raw 11 as total 11 despite +4. | The requested mechanic was exercised and its known modifier was omitted. |
| TW-F29 | NC01 arrival over-executed the travel beat. | MECHANIC-DEFECT | `46f-r6-retry5/relay/protocol.ndjson:20561` narrates passage beyond the cave despite stop-at-approach intent; `:20609` still commits NC01. | Narration performed future movement beyond the committed one-beat destination. |
| TW-F30 | Kira died during a completed NC01 victory. | DESIGN-WORKING | Combat ends successfully at `46f-r6-retry5/relay/protocol.ndjson:27441`; state at `:27521` records the earned XP and surviving PC. | The party won at level 1. Kira's death and the player's later reload are valid consequences/choices, not a mechanic failure. |
| TW-F31 | Second Wind charge consumed without healing. | MECHANIC-DEFECT | Declaration/request/result/state are at `46f-r6-retry5/relay/protocol.ndjson:31831-32076`; usage becomes 0 while HP receives no Second Wind increase. | This is silent authoritative resource/HP divergence on an exercised class feature. |
| TW-F32 | Bex died in NC02's five-enemy fight. | DESIGN-WORKING | Encounter opens at `46f-r6-retry5/relay/protocol.ndjson:31473`, Bex falls at `:31800`, and Alaric/Kira win at `:33997-34279`. | The encounter was winnable at level 1. Companion death and choosing to reload do not establish broken balance. |
| TW-F33 | Bex died before Alaric acted in NC03. | DESIGN-WORKING | `46f-r6-retry6/relay/protocol.ndjson:3568-3738` shows the generated threats and lethal owlbear attack. | A lethal initiative outcome is not by itself a defect. The route was later bypassed in ordinary play. |
| TW-F34 | NC04-to-Nexus request moved to NC02. | MECHANIC-DEFECT | State at `46f-r6-retry8/relay/protocol.ndjson:1983` is NC04; narration/state at `:2394-2442` commit NC02 after the Nexus request. | The travel mechanic committed the wrong destination. |
| TW-F35 | Initial NC05 roster overwhelmed the level-1 party. | PLAYER-PLAY | Failed Arcana creates the encounter at `46f-r6-retry8/relay/protocol.ndjson:4393-6186`; combat reaches 0 HP at `:6995-7061`. Final victory is recorded at `46f-r6-retry40/relay/protocol.ndjson:3668-3752`. | Repeatedly taking the finale at level 1, after bypassing XP-bearing paths, produced hard fights. The same campaign was completed; lethality is not a defect. |
| TW-F36 | Discharge narration falsely put Bex at 0 HP. | MECHANIC-DEFECT | `46f-r6-retry10/relay/protocol.ndjson:3560` narrates unconscious Bex; `:4316-4364` shows her alive at 4 HP. | Visible outcome and authoritative character state directly conflict. |
| TW-F37 | Guarded short rest consumed an hour but healed nothing. | MECHANIC-DEFECT | `46f-r6-retry10/relay/protocol.ndjson:4772` says the hour completed and no recovery was recorded; `:5028` retains 5 HP and the same 19:15 clock. | The game accepted and narrated a completed rest but committed neither time nor its requested recovery workflow. |
| TW-F38 | Withered Hart cleansing entered the name loop. | MECHANIC-DEFECT | `46f-r6-retry36/relay/protocol.ndjson:5374-5816` shows normal model completions through retry 11 without a terminal; the same name-normalization conflict as TW-F11 is present. | An exercised quest action became an unbounded deterministic correction loop. |
| TW-F39 | Long-rest prose did not match HP/time state. | MECHANIC-DEFECT | `46f-r6-retry39/relay/protocol.ndjson` records the eight-hour recovery narration while subsequent state remains 00:25 with Kira 8/15 and Bex 4/12; the later Second Wind is a separate committed recovery. | A narrated completed long rest made no authoritative time/HP change. |
| TW-F40 | Text `Load` was intercepted at 0 HP. | MECHANIC-DEFECT | `46f-r6-retry38/relay/protocol.ndjson` records `Load` rejected by the incapacitated guard; the following relay's headless restore succeeds. | Load is explicitly a recovery control, not a gameplay action the unconscious-PC guard may reject. |
| TW-F41 | Attack adjudication contradicted submitted rolls. | MECHANIC-DEFECT | The low-total hit is in `46f-r6-retry38/relay/protocol.ndjson:6967-7258`; the natural-20 no-damage narration is in `46f-r6-retry40/relay/protocol.ndjson` during NC05-E2 before final XP at `:3752`. | These are exercised attack-resolution contradictions, independent of whether the party ultimately won. |
| TW-F42 | NC05 roster varied from five hostiles to Malarok alone. | REPEAT-INDUCED | The large roster is visible at `46f-r6-retry8/relay/protocol.ndjson:6186-6631`; the final encounter's Malarok-only turns and completion are at `46f-r6-retry40/relay/protocol.ndjson:3016-3752`. Authored context in the captured prompt at `46f-r6-retry18/relay/protocol.ndjson:749` lists Malarok 1, bodyguards 2-4, wolves 2-4. | The authored scene did not specify a Malarok-only default. Material roster collapse appeared only after many reload/retry story iterations, so the evidence supports retry-context residue, not normal fixed encounter variance. |
| TW-F43 | Final afternoon prose contradicted 03:55/night. | MECHANIC-DEFECT | Final state is 03:55/night in `46f-r6-retry40/relay/protocol.ndjson` after completion; final arrival history is `conversation_history.json:157` and describes afternoon mist. | Player-visible time-of-day contradicts authoritative clock. |
| PK-023 | At 300/300 XP, required level progression was broken. | UNTESTED-CLAIM | `BUG_LEDGER.md:192-198` proves eligibility and absence of an emitted `levelUp`, but a scan of the Pumpkin King player inputs finds no level-up request. Thornwood commands likewise contain no advancement request, and final state is only 196/300 at `46f-r6-retry40/relay/protocol.ndjson:3751-3752`. | Automatic milestone emission may be a content/prompt expectation, but the actual level-up interaction was never attempted and refused. The evidence cannot support "level-up mechanic broken." |

## XP accounting for the completed Thornwood lineage

The completed lineage's durable XP progression is:

| Step | XP before -> after | Evidence | Outcome |
|---|---:|---|---|
| Scout's Watch Twig Blights | 0 -> 16 | `46f-r6-retry4/relay/protocol.ndjson:3324-3325` | Two Twig Blights defeated; transcript history says 50 party XP divided to 16 each. |
| North Tower ambush RO06-E1 | 16 -> 32 | `46f-r6-retry5/relay/protocol.ndjson:7609-7610` | First two-bandit encounter completed; E2 is already active in the state. |
| Repeated North Tower ambush RO06-E2 | 32 -> 48 | `46f-r6-retry5/relay/protocol.ndjson:8953-9041` | Second two-bandit encounter completed; this award is arithmetically consistent but the duplicate encounter is REPEAT-INDUCED. |
| Captive-hut sentries TW05-E1 | 48 -> 64 | `46f-r6-retry5/relay/protocol.ndjson:17369-17370` | Two sentries defeated and captives rescued. |
| Restores discard doomed-branch XP | back to 64 | `46f-r6-retry5/relay/protocol.ndjson:27521-28159` and `46f-r6-retry31/relay/protocol.ndjson:3865-4349` | NC01 and failed Nexus branch awards disappear because the player restored an earlier save. This is expected restore behavior. |
| Isolated elite bodyguard NC05-E1 | 64 -> 130 | `46f-r6-retry31/relay/protocol.ndjson:6605-6693` | A real encounter was completed and awarded 66 XP to each party member. |
| Malarok NC05-E2 | 130 -> 196 | `46f-r6-retry40/relay/protocol.ndjson:3668-3752` | Malarok defeated; 200 party XP divided to 66 each. |

Arithmetic: `16 + 16 + 16 + 16 + 66 + 66 = 196`. No completed-lineage
transcript shows lost XP or a bad sum. One 16-XP award is downstream of the duplicated
RO06 encounter and is therefore suspicious as repeat-induced content, but it is not an
arithmetic error. Peacefully bypassed NC01/NC02/NC03 encounters correctly produced no
combat XP. XP from battles later erased by Load correctly did not survive into the
completed lineage.

## Level-up initiation

The captured main-model contract exposes `levelUp` as the action for advancement (for
example `46f-r6-retry40/relay/protocol.ndjson:234`). Neither the Thornwood
`commands.ndjson` corpus nor the Pumpkin King input artifacts contain a request such as
"level up," "advance my character," or "Kira needs to level up." Thornwood never reached
the threshold at all. Pumpkin King reached 300/300, but the player did not use the player
screen to request advancement or correct the DM.

Therefore:

- Thornwood "level-up broken" is UNTESTED and factually inapplicable at 196/300.
- Pumpkin King proves that an automatic milestone `levelUp` action was not emitted. It
  does not prove the actual level-up mechanic fails when invoked, so PK-023's systemic
  mechanic conclusion is UNTESTED-CLAIM rather than MECHANIC-DEFECT.

## Difficulty, roster, deaths, and reloads

- NC01 was won at level 1 (`46f-r6-retry5:27441`), with Kira dead.
- NC02 was won at level 1 (`46f-r6-retry5:34279`), with Bex dead.
- NC01, NC02, and NC03 were also bypassed through normal route choices, as the final
  conversation's location summaries show (`conversation_history.json:70-103`).
- The NC05 large roster was lethal, but the party repeatedly approached the finale at
  level 1. The final Malarok fight was won. This disproves "unwinnable."
- Companion deaths and the choice to Load afterward are DESIGN-WORKING. The separate
  down-state freeze, ignored successful check, attack-resolution errors, or stale restore
  context remain defects because those are exercised mechanical failures.
- The Malarok-only roster after roughly forty retries is not supported as normal authored
  variance: captured canonical context specifies Malarok plus ranges of bodyguards and
  wolves. It is best classified REPEAT-INDUCED pending a fresh no-retry comparison.

## Reload hygiene

Two genuine retry/restore classes manifested:

1. Restore left later-scene conversational authority over earlier authoritative state
   (`46f-r5-replay:184,401`).
2. Repeated investigation/retry created duplicate encounter IDs and rewards (RO06-E1/E2),
   while extensive Nexus retries eventually produced a materially collapsed roster.

Those survive this review as REPEAT-INDUCED findings. Loading itself, rolling back doomed
branch XP, retrying after deaths, and eventually obtaining a successful tactical result are
normal game behavior.

## Final disposition

Previously claimed systemic defects that dissolve:

- "Thornwood level-up is broken": UNTESTED; threshold never reached.
- "Thornwood finale is unwinnable": disproven by the completed run and strongly shaped by
  level-1 route choices/retries.
- NC01/NC02/NC03 lethality and companion deaths: challenge working, not defects.
- Kira declining target advice: independent companion agency working.
- XP 196/300: correct arithmetic for the committed completed lineage, not lost XP.

Previously claimed issues that survive as exercised defects are the narrow rows marked
MECHANIC-DEFECT above. The most consequential are the 0-HP recovery seam, ignored check
outcome, canonical-name loops, unsatisfiable item/NPC construction contracts, wrong travel
destinations, partial plot/reward commits, roll/adjudication errors, and rest/state
divergence. Restore contamination, duplicate encounters/rewards, and late roster collapse
survive separately as REPEAT-INDUCED rather than evidence that ordinary lethality or the
level-up mechanic is broken.

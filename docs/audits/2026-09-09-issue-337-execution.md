# #337 stage-one execution record

Status: IMPLEMENTED; focused native/WSL checks passed. Original real TW05 hostile
candidate accepted and combat returned a player prompt. C4 independent code/PX
reviews pass the #337 slice; separate failures and unrun extensions remain explicit
below. Owner has authorized commit and publication to main after validation.
This is not an unconditional game-wide PASS.

## Authority and isolation

Owner D-337-2 in live #193 Part 5 authorizes execution of reviewed plan
`2026-09-09-issue-337-canonical-scene-plan.md`, SHA256
`f32494fe2b2aed32ac5ee92d1c717a404f1899378cf4e35916333dec05ce927d`.
The frozen plan's pending-execution row is historical; this record records the
subsequent approval without changing the reviewed artifact.

Worktree: `/home/loup/neq-worktrees/337-canonical-scene-plan`.
Implementation branch: `fix/337-canonical-scene-evidence`.
Baseline: `e754edefb44b550f14121b76fb2829bf2d11d419` (revision evidence only).
Production scope: `main.py`, additive 53 lines. The owner subsequently authorized
commit and push to main: "if we've valdiated the narrow fix of rth open issue works
go ahea dan comit and push it up tot eh tip of main". #279/PR339 and #342 remain
separate. No unrelated repair is included.

## C0-C2 and correction

- Main candidate SHA256:
  `00a2e0b247682bc563ee7f2e8a1045833bd3dd5156e01fe9571ab1cc50352f89`.
- Complete native export matches tracked worktree source; original authentic save
  copy matches all 24 source files. See `C0-manifest.json` below.
- Native interpreter: Windows Python 3.12.3 at `C:/Python312/python.exe`, OpenAI
  SDK 2.1.0; effective provider OpenAI. No model/effort tuning.
- Python compilation passed WSL and native Windows; `git diff --check` passed.
- EOL preserved: baseline 10,700 LF-only lines, candidate 10,753 LF-only lines;
  zero CRLF both, all added source characters ASCII. Independent recheck removed
  only the addition and reproduced baseline bytes exactly.
- Nineteen pure source-selection/serialization checks passed on both platforms.
  These are development checks, not mocked or real gameplay acceptance.
- Pyflakes baseline comparison: zero new diagnostics. Existing diagnostics remain
  outside this scope; line-number shifts are normalized in the comparison.
- Independent code review found cancelled-travel metadata incorrectly selected as
  a prospective destination in the first candidate. Corrected to the existing
  typed `reason_code == "approved"` predicate; cancellation/intermediate/absent
  reason cases now prove origin-only evidence. No scope expansion or new guard on
  gameplay: this selects evidence, not permission to move.
- Independent No-Limits and Single-Path initial candidate scans passed; their
  original hashes are retained honestly. Final correction confirmation passed
  on candidate00a2e0b2, including source producer trace and all pure checks.

## Evidence inventory

Local private evidence root: `/mnt/c/337-ev-qdSV6b`.
Native source: `/mnt/c/337-src-CWxHLg` (physical export, no invalid Git pointer).
Native game: `/mnt/c/337-game-MuORU7`.
Original save source (never modified):
`/mnt/c/vra-native/voice_ship_0214cbdf/debug/voice_ship_0214cbdf/game/modules/The_Thornwood_Watch/saved_games/save_20260902_185213`.

This is an authentic essential save at RO01, 09:00, before TW05, with Eirik Vane
and six companions. It is not a full-history save; no claim is made that its absent
conversation was restored. The fresh game receives current source prompts through
the production bootstrap. Prompt bytes as loaded must be verified after startup.

- `C0-manifest.json`: baseline, candidate, export comparison, all source-save hashes,
  metadata, prompt hashes, undefined-name delta.
- `checks.py`, `dev-wsl.json`, `dev-native.json`: pure checks and results.
- `original/T065.json`, `T067.json`, `T096.json`, `T097.json`: preserved historical
  real captures. The approved plan gives exact zero-based indices and findings.
- `review-code.md`: first candidate blocker; not a current-code failure verdict.
- `review-limits.md`, `review-single.md`: initial static sentinel approvals.
- `review-correction.md`: final correction recheck PASSED, no gameplay claim.
- `PARTIAL-VERDICT.md`, `live-summary.json`, `call-timings.md`,
  `player-transcript.md`: actual native partial acceptance, all 40 captured calls,
  exact narration, parsed consumer checks and remaining gates.
- `A1/protocol.ndjson`, `A1/model_captures`, `A1/state_snapshots`: raw artifacts.

## Initial partial acceptance (historical, superseded by continuation below)

A0 original real captures are preserved. One actual native conversation turn ran:
three T065 packets contain the exact full RO01 record; raw player input/candidate
adjacency preserved. Negative semantics fired twice and corrected before publication.
The final narration asks for the player's Persuasion roll; rejected stronghold
information/plot updates did not enter accepted fiction or canonical progress.

This is partial A2/A4 evidence, not full-arm success. A1 TW05 boss/trap, A3 travel,
A5 XP, A4 Load/relaunch/in-flight cancellation and A2 pit-discovery polarity remain
NOT-REACHED. No all-green claim; C4 final audit remains pending.

Separate #343 was observed: all 24 real T107 completed outputs have voice:string
but the unchanged runtime expects voice:object; 12 profile fallbacks within this
turn. The turn completed after 164.518s. C3 directs stop/report new defects, so no
profile repair or further gameplay was attempted. The existing semantic layer did
continue; this is not evidence that #337 caused a crash or failed its own gate.

Supported Save succeeded (seq710) and Quit succeeded (seq713); process exit0,
native PID36060 gone, zero matching remaining processes. Full game remains at RO01
before Persuasion roll. Original save and all 27 loaded prompt hashes reverified.
Resume the original vertical slice or fix #343 separately only after owner direction.
Independent partial player review completed: `review-partial-px.md` confirms the
narrow real consumer/semantic/agency/history results and five grounded claims.
Pacing FAILED: 55.758s to first visible progress, then 54.777s from narration to
next prompt. Those observed quiet gaps accompany profile-fallback passes; added
to #343, not claimed as a #337 regression. No unrun arm was certified.

## Resume pointers

Owner subsequently said "yes contuneu and keep it searte": continue C3 with #343
separate, no companion repair. Native continuation evidence: A1-resume, PID40736,
same source/game and candidate00a2e0b2. Initial relaunch resumed the unresolved
interrogation. Genuine Persuasion d20=6 + Charisma1 =7 was submitted; failure
returned control without revealing the clue or advancing plot (seq544/601).

The original A1 process and A1-resume process are stopped. A1-afterload is the
current continuation on the unchanged source export. For future relaunch use
`C:/agent-room-fleet-kit/local-data/311-native-relay.py` with source, game, and a new
evidence path. Protocol input is `{"type":"input","content":"..."}`; native console
submission requires Enter/CR. Read the actual restored response before choosing the
next action. Generate genuine die results only
when prompted and apply the sheet's actual modifier. Continue through normal play,
not authored-location omniscience or state edits. Do not reset this preserved game
or copy private config/captures into tracked changes.

### Continuation, 2026-09-09 (partial, still in progress)

Raw artifacts are under `A1-resume` and `A1-afterload` in the same evidence root.
T065 indices below are zero-based in A1-resume/model_captures/T065.json.

- Intimidation16 produced the real Stronghold clue (seq1027); PP001 advanced only
  after success. T065[2] rejected invented Thornwood Bastion; [3] accepted correction.
- Real RO01->RO06 travel: T065[4] contains origin and approved prospective records;
  seq1408 arrival and prompt1462 snapshot agree on RO06.
- Actual Perception17 exceeded RO06 DC13. T065[7] rejected an ambiguous discovery;
  [8] accepted disclosure of the two concealed bandits, with player agency intact.
  Earlier incorrect PC-modifier rejection is separate #344, not repaired here.
- Player chose combat; T065[9] approved authored Bandit x2. Real attack and damage
  dice were requested, rolled, and submitted separately. Two enemies defeated,
  all six companions alive, XP7 on all seven saved character sheets. Seq4798/4891
  returned to normal play. This is ordinary-bandit evidence, not Gorvek/boss XP.
- Save `save_20260909_184415` captured the clean postcombat boundary. During subsequent
  approved RO06->TW01 travel, basename-based Load was accepted_deferred, then
  selected_applied (seq5267), then restart (5269). Restored party bytes equal the
  saved checkpoint; A1-afterload welcome387 correctly resumes RO06/XP7. An initial
  absolute-path save identifier was a rejected harness input, not valid-Load failure.
- T065 was already complete when Load arrived; exact T065-in-flight cancellation
  remains NOT-REACHED. Postcommit travel cancellation and actual restore are proven.
- A1-afterload travel then arrived at TW01/09:40 (prompt746), preserving XP7.
- Independent continuation PX review confirms these narrow results and five
  grounded narration claims. It does not certify the outstanding TW05 boss/pit arm.
- Existing weather-loss #187 and profile #343 remain separate. Two T097 narration
  consistency observations are being reconciled against existing #275; no repair.
- A1-afterload continued to TW02: T065 originTW01/prospectiveTW02, arrival1451,
  prompt1509. The next cautious-advance response prematurely revealed a rope snare;
  T065 rejected this against the authored Perception DC14. Accepted narration1741
  asks for Perception without confirming a discovered trap. Genuine d20=15 prepared
  for total18, but not submitted before the next prompt. This is a real concealed-
  trap negative control, not a claim that TW05's different pit arm was reached.
- Postnarration work then waited several minutes with updating provider status.
  Native parent26072 had child2224, with an established HTTPS connection on443.
  Read-only process checks only; no kill, model change, or repair. Full TW05 proof
  remains pending. See raw A1-afterload protocol1741 onward for exact wait timings.
- That wait terminated through the existing T107 unavailable/fallback at1778;
  normal prompt1817 followed. Perception18 was submitted only afterward. T065[8]
  approved detection against DC14; narration1984 reveals the intact snare and offers
  disable/bypass/search. Bypass was chosen; narration2244 leaves it undisturbed,
  time advances five minutes, normal prompt2339. Subsequent explicit travel toward
  the Stronghold is now pending through another profile/provider wait.
- Separate narration observations remain observations, not proof of wrong-target
  resolution: the reviewer noted prior-wound wording and stale companion advice.
  Existing #275 covers T097 factual continuity; no prompt/voice/resolver repair is
  included here and no additional independent mechanism is asserted from wording.

## Completed continuation: original TW05 reached

Same main.py SHA00a2e0b2 throughout. `A1-afterload/EVIDENCE_INDEX.md` contains every
retained model result with duration/tokens and all player text, JSON-escaped verbatim.
`A1-resume/EVIDENCE_INDEX.md` covers the preceding route, bandit fight and Load.

| Arm | Current disposition | Actual evidence |
|---|---|---|
| A0 source/forensics | PASSED | original real packets; C0 manifest; 19 source-selection checks native/WSL |
| A1 original hostile vertical slice | PASSED independently confirmed | afterload T065[11] wrong pit save rejected, [12] accepts corrected createEncounter including Gorvek as monster; real T096[0..4], T097[0], player prompt5084 |
| A2 semantic rejection/correction | PASSED controller checks | wrong saveDC15->13, hidden TW02 snare premature disclosure rejected[6], earned roll18/DC14 approved[8]; originals/corrections retained |
| A3 origin/prospective travel | PASSED | RO01->RO06, RO06->TW01, TW01->TW02 and TW02->TW05 actual packets, commits and arrivals |
| A4 save/load/relaunch/normal turn | PASSED reached portions | resume5267 selected_applied/restart5269; afterload387 restored RO06; subsequent travel and real turns; final Save5184 and Quit5192/exit0 |
| A4 exact T065-in-flight cancellation | NOT-REACHED | Load arrived after T065 during travel apply; do not mislabel as in-flight-review proof |
| A5 boss defeat/XP extension | NOT-REACHED | stopped at first actual player turn with Gorvek alive; no XP repair/award claim |
| PX pacing | FAILED separately | existing343 profile fallback path, including two ~600s waits; unchanged by337 |
| C4 five-point candidate audit | PASSED | independent code and player evidence reviewers; no landed-commit claim |
| Pit roll handoff into combat | FAILED separately, #345 | requested save2953 not collected before NPC batch5038/ordinary prompt5084; later recovery NOT-REACHED |

The decisive accepted T065 invocation is `4afda443-f3b8-43a0-ad7b-fd45b38b4f4c`.
It contains the entire current TW05 record: both Gorvek lists, authored defender
quantities, all pit fields and other location keys. Candidate contains two sentries,
two warriors and Bandit Captain Gorvek as monsters, six actual companion NPCs, and
an explicit hostile typed scene. Rejection[11] is about the pit's saving throw,
not Gorvek being listed as an NPC. Correction[12] approves DC13 and that roster.
Delivered main text2953, actual combat intro4852, T0975038, player prompt5084.

Encounter `modules/encounters/encounter_TW05-E1.json` records Gorvek as type enemy,
faction hostile, monsterType bandit_captain_gorvek, 52HP. Its actual module monster
sheet has challengeRating2. T096 proposed real hostile interactions and retained
its corrections; no claim that all separate spell/resolver mechanics were repaired.

Final supported save `save_20260909_193926` copied41 essential files, result5184.
Quit result5188, exit5192, native exit0; relay also exited0. Read-only native process
scan found no parent26072 or child of that parent remaining. All27 loaded prompt
hashes and all24 original-source-save hashes reverified equal to C0. No test state
edits, model tuning, artificial provider replies or unrelated product repair.

Original hostile turn wall time196.728s. Two earlier turns took769.577s and805.156s
with existing post-/pre-DM T107 profile waits and visible provider heartbeats. These
are measured end-to-end times, not T065 latency: decisive T065[12] was7.377s.
All selected bindings/tokens are in the index; actual response.model and dollar
cost delta remain UNKNOWN. Full evidence has real input-size cost, not zero-cost.

Final C4 artifacts: `review-final-code.md`, `review-final-px.md`,
`FINAL-VERDICT.md` in the private evidence root. Independent code review reran all19
pure checks and confirmed the unchanged guards/single path/no new limits. PX traced
five narration claims, actual monster-backed Gorvek targets, all five initial T096
full-health enemy snapshots and seven final authoritative events. No double damage
or inherited enemy injury was established. Existing275 narration-attribution
observations remain separate, not fabricated as a new resolver failure.

New observed #345 (https://github.com/MoonlightByte/NeverEndingQuest/issues/345):
main narration asks a pit Dex save, then createEncounter advances NPC actions before
collecting it. Saved pendingTurn:null/awaiting_actor, no pit event, PC14HP. This is
an immediate handoff failure, not proof of permanent loss or #337 introduction.
Filed separately under the owner's scope instruction; no extra product change.

## Narrow-scope closeout confirmation (2026-09-09)

Owner continuation: "okay, contineu and keep 337 narrow". The subsequent generator
compatibility inspection does not expand this patch. Private evidence:
`/mnt/c/337-ev-qdSV6b/MODULE-COMPAT-REVIEW.md` and `MODULE_COMPAT_RESULTS.json`.
The authentic TW05 location and generated encounter/monster sheets pass their
current runtime schemas. That is structural compatibility, not a guarantee of
every authored boss mechanic. The unrelated NC05 dangerLevel enum discrepancy and
authored-to-generated monster fidelity questions remain report-only, outside #337.
No starter module, generator, monster sheet, prompt, or schema was changed.

Final closeout rerun: all19 focused pure-value checks PASS in both WSL and native
Windows; git diff --check PASS. Candidate main.py SHA256 remains
`00a2e0b247682bc563ee7f2e8a1045833bd3dd5156e01fe9571ab1cc50352f89`.
These checks supplement, not replace, the real native OpenAI acceptance above.
Implementation and scoped acceptance are complete; publication remains a separate
owner gate. No additional live run, commit, push, merge or issue closure performed.

## Resolution ledger

| Finding | Disposition |
|---|---|
| Missing full canonical location evidence | task-C1 implemented; real RO01 and TW05 consumer proof, original hostile candidate accepted |
| Cancelled-travel phantom destination in first candidate | task-C2 corrected; independent recheck PASSED |
| General combat side/XP semantics | override: D-337-1 separate #279/PR339 stage |
| Diagnostic-write fail-stop | issue-#342; no repair here |
| T107 nested voice shape absent from prompt, real profile degradation | issue-#343; owner authorized continuation separately; no repair here |
| PC Perception modifier rejected without character-sheet authority | issue-#344; no repair here |
| Travel world-condition loss | existing issue-#187; no repair here |
| T097 prior-state/stale-advice wording observations | existing issue-#275 context; no new resolver-failure claim or repair |
| Pit saving throw request crosses combat entry without collection | issue-#345; no repair here, later recovery NOT-REACHED |
| Execution authority | override: D-337-2 granted after full plan review |
| Publication authority | owner approved commit and push to main after scoped acceptance; latest main rechecked before publication |

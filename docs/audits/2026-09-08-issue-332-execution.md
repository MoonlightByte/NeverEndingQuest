# Issue 332 execution and acceptance

Owner approved execution after eight-seat review and clean confirmation of
plan c41656abfb1f3cacf45baa6740bcc0856160e786a4b8fcd91702d9232004193d.
Authority recorded live in #193 Part 5 D-332-1 on 2026-09-08. This supersedes
the frozen plan's pending-execution status only, not its reviewed mechanics.
Main publication is NOT authorized.

Base: 6916507c74d4bbb4795ad9529a69d33c3ce4efe0, origin/main ancestry verified.
Worktree /home/loup/neq-worktrees/332-plot-validator-plan.

## C0/C1

Live #193 Part 1 and relevant Part 2 p8-p13 reread; D-332-1 appended to current
live issue without replacing unrelated rulings. Gameplay guidelines read from
/mnt/c/dungeon_master_v1/docs/testing/GAMEPLAY_GUIDELINES_FOR_AGENT_PLAYERS.md.
Frozen plan and complete review read before implementation.
One additive main.py evidence block implemented; no other production file.
No existing prompt/validator/writer/schema/transport branch changed.
Focused gates, simplifier and live acceptance pending below; no PASS inferred.

## C2 focused development gates

- WSL and native Windows Python 3.12 py_compile PASSED.
- 15 pure JSON/I/O/assembly cases passed on both runtimes using local
  local-data/332-primitives.py. No game/provider imports or fabricated narration.
- Removing the additive block restores every original main.py byte, including
  line endings; 39 ASCII lines added, no existing bytes changed.
- Pyflakes has zero undefined names and identical baseline warning multiset.
  Initial comparison failed only because a pre-existing redefinition warning's
  embedded source-line reference shifted by 39; the local comparator now
  normalizes that reference. No product change was made to satisfy that check.
- Independent 332_impl_simplifier PASSED, no slimming recommended. Raw candidate
  No-Limits/Single-Path scans empty; all eight whole-file hits inherited nonpayload
  excerpts/comparison keys. No lock, numeric bound or provider call added.
- Source export/prompt equality: 288 present runtime/prompt/schema files compared
  to the worktree, zero mismatches; game prompt directory refreshed and compared.

Native source /mnt/c/332-native-src-D3ahWA; game /mnt/c/332-game-wS56ph.
Evidence /mnt/c/agent-room-fleet-kit/local-data/332-acceptance-7Tjnl2.
main.py SHA256 86fd53291c4904bcdb0389269f9385b4ef2a8da65c4c26c7ac9a5f8749fa509d.
Source+game copies occupy about 47 MB, excluding old debug/backups/saved-games.
Original #322 game untouched. Its original four captured calls are copied into
original-524-527.json; baseline.json records source/prompt identities.
The copied game is the real successful #322 saved-state Load/relaunch at A05,
11:51, before the post-Save greeting. No canonical game values were edited.

The existing native 311-native-relay.py runs run_headless.py serve and forwards
manual commands only (no observer/control modes enabled). It captures complete
NDJSON and provider artifacts. Completed gameplay results follow.

## C3 live acceptance (local commit e95bc243)

All inputs were manual single requests at real prompts, OpenAI only, native
Windows run_headless.py serve. Original fixture untouched. No model responses
or canonical state were fabricated. One initial relay input used the wrong
`text` key, was rejected before engine intake, then was sent once correctly
with `content`; that is a harness setup error, not a failed gameplay turn.

- A1 PASSED: actual T067 master row4 proposed updateTime(5) and PP005 impact;
  T065 row5 received the complete canonical current-module plot and accepted.
  Independent parsed comparison equals before-A1 disk, including all five
  main and all five nested side-quest IDs. Raw user/candidate pair exact and
  adjacent, existing hub evidence preserved. T077 invocation
  32d6a6b3-413b-40ec-bbd1-dc22801b0a2c persisted PP005 only. Clock11:51->11:56,
  location/roster/characters/rewards unchanged. Narration457, next prompt630.
- A2 main impact PASSED via A1. Nested-SQ impact PASSED naturally via A3:
  T067 row8 proposed SQ001 not-started with conversation impact; T065 row9
  accepted, T077 invocation16e498a5-bda2-409f-88c6-60abb9e54b65 wrote nested
  SQ001 only. All sibling/authored fields unchanged. Status advancement is
  NOT-REACHED, not implied by an impact-only write.
- A3 player reward/completion denial PASSED. Player asked for payment while
  admitting no investigation. Cira refused; no reward/HP/XP/time/status change.
  Narration849, prompt995. T067 already refused, so T065 rejection of a false
  completion candidate is NOT-REACHED. This is not a blanket semantic PASS:
  the accepted impact conflates NPC refusal with the player's voluntary
  refusal, separately filed as #333 with independent PX evidence.
- Natural rejection/correction PASSED during A4 quiet turn: T067 row12 added
  an unsupported injury. T065 row13 rejected it; T067 row14 removed it; T065
  row15 accepted. Only accepted narration delivered at1657; next prompt1781.
  Canonical evidence remained in both review requests. This proves the
  existing correction path still fires, not every possible rejection class.
- A4 Save and Load application PASSED: Save result1382; quiet turn changed
  SQ001 impact after Save; Load result1803 selected_applied, 185 files restored,
  clean restart exit1805 and process return0. Snapshot after-load-before-restart
  module plot and tracker are byte-identical to after-A3 saved values, not the
  newer quiet turn. Companion sidecars restored to saved hashes. Native
  relaunch welcome completed. Post-Load T067 row19 proposed no actions; T065
  row20 accepted using restored plot evidence. Narration451/prompt541 in
  A4-restart; Quit544/exit546, process return0. Both relays exited normally
  after their stdin loops were released; final native process scan found0
  matching game/relay/direct-child processes. Receipt: quiescence.txt.

T077 is present in actual per-call model captures but absent from the master
JSONL endpoint log; cite its invocation rather than inventing a master row.
Provider response.model absent in these captures. Actual selected bindings:
T067 luna/none, T065 luna/low. All timings and full player text remain local.

## Separate observed findings (no repair in this branch)

- #333: accepted plot impact misattributes Cira's refusal as party declining
  payment. Root cause/lineage not inferred from one sample. Player safety and
  source identity PASS do not certify all summary prose.
- #334: authentic saved activeQuests says SQ003 not started while canonical
  module plot says completed, both before and after A1. Existing discrepancy;
  current writer cause and user-visible consequence need separate investigation.
- Existing repeated compression BEAT_MALFORMED diagnostics and T107 grounded
  fallback were observed; no compression/voice code changed or repaired.
  Disposition FYI, not a newly diagnosed defect: these are fallback/validation
  diagnostic events, not proof of lost data or a failed player turn. Telemetry
  distinguishes repeated historical rows from live validation failures.

## Measured performance and honest limits

Actual selected OpenAI call timings (seconds); end-to-end includes the existing
voice/context/compression pipeline, not just T065. These are observations, not
a controlled before/after latency comparison or a whole-game benchmark.

| Real turn | T067 | T065 | T077 | Input to narration / prompt |
| --- | --- | --- | --- | --- |
| A1 main plot | 6.725 | 7.688 | 3.630 | 102.654 / 145.182 |
| A3 nested-SQ / deny reward | 5.676 | 5.448 | 3.301 | 104.852 / 140.830 |
| A4 quiet, real correction | 5.917 + 7.459 | 5.664 + 6.011 | 4.108 | 172.985 / 202.495 |
| A4 post-Load | 5.446 | 4.615 | none (no action) | 83.225 / 104.463 |

New evidence message5923-6186 UTF-8 bytes; estimated o200k content tokens
1378-1435, excluding role/framing. Actual T065 prompt-token counts26462,
26784,24400,24491 for the first four calls are whole-request measurements.
Exact per-call tokens, full verbatim player text, input-relative timestamps,
failure-pattern counts and payload comparisons are in local artifacts:
193-independent-telemetry-summary.txt, A1-analysis.json, A4-restart-analysis.json,
A1-master.jsonl, final-master.jsonl and both protocol.ndjson files.
Analyzer same_as_before_A1=false for later requests is expected: each must
match ITS before-turn snapshot, not the first turn's earlier plot.

NOT-REACHED: actual quest status advancement; invalid-completion-candidate
rejection (the generator refused first); cross-module travel/scope switch;
Load/cancellation during active validation. Missing/malformed evidence and
local-provider template-tail variants have pure primitive checks ONLY, not
live-gameplay verdicts. No Gemma run and no blanket all-model semantic claim.
Original rumor correctness and all newly narrated facts are not proven merely
because the canonical ID was accepted. Thane's HP was23/50 with no recorded
injuries; the correction test proves the reviewer fired and its change stayed
isolated, not a general finding that he was fully healthy.

## C4 final independent audit

Independent final post-Load PX PASSED: current inn and companion presence match
disk; Town Square recalls the restored SQ001 impact; quest remains unresolved;
no reward/time/HP/XP change. T067 actions empty and plot/tracker/character files
byte-identical across this turn. Entire after-load-before-restart snapshot equals
after-A3, while SQ001 impact differs from after-quiet, proving actual restoration.
Quiet-turn rejection/correction independently verified against accepted durable
history. Independent non-author332_impl_simplifier completed NEQ-REVIEW-15:

1. SPEC COVERAGE PASSED: exact implementation and planned evidence accounted for.
2. LEDGER CLOSURE PASSED: F1-F4 resolved, D332-1 ruled, findings333/334 filed.
3. TRACKED FOLLOW-UPS PASSED:331/326/329/317/318 remain open and accurate.
4. R3/SENTINEL RE-RUNS PASSED:15 primitives, no undefined names/new warnings,
   both raw diff scans empty, baseline bytes/EOL preserved.
5. BUG-LAYER ACCEPTANCE PASSED WITH DOCUMENTED BOUNDARIES above; final PX read.

Raw output/artifact:193-independent-postimplementation-audit.txt; reproducible
checks:193-independent-audit-checks.py, both under the local evidence root.
The audit inspected codee95bc243 and evidence commit55ca6fc1; final changes
after that are documentation only. No in-scope blocker. No push, main merge,
automatic issue closure, or unrelated product repair is authorized by this record.

## Owner shipment approval

After the completed-test summary and its explicit untested-branch limits, the
owner authorized committing and pushing to main. This supersedes the earlier
publication hold only; it does not change the scoped verdicts or authorize any
additional repair. Immediately before publication, fetched origin/main still
equaled the tested base6916507c, so publication is a conflict-free fast-forward.
The15 pure checks passed again on WSL and native Windows, compilation passed,
static warnings were unchanged with zero undefined names, and diff-check passed.
The production main.py hash remains86fd53291c4904bcdb0389269f9385b4ef2a8da65c4c26c7ac9a5f8749fa509d,
identical to live acceptance. No repeat provider run is claimed for this docs-only
shipment record. Other agents' worktrees and local main checkout are untouched.

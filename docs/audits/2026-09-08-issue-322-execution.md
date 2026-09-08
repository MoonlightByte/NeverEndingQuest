# Issues 322 and 328 execution and acceptance

## C0 authority and baseline

Owner approved execution and thorough testing after plan presentation, 2026-09-08.
Live #193 Part5 D-322-1 records that ruling; D-322-2 records coupled scope.
Frozen reviewed plan SHA256:
2d60ce66b984aef1fc4d607cef505adc7c194663797cb18cf4ac39a1d2ad4d0d.
Its historical execution-open status is superseded by this ruling, not silently
rewritten into the previously reviewed artifact. No merge/push authorized.

Worktree: /home/loup/neq-worktrees/322-campaign-export-plan.
Implementation branch: fix/322-campaign-export-hubs.
Fresh git fetch origin main: HEAD=origin/main6d18d09b, ancestry PASS.
Only reviewed plan/review docs were untracked before work. Three source files
are LF; preserve regional bytes. Python3 pyflakes available; native Windows
C:/Python312/python.exe is3.12.3 with OpenAI and psutil importable.

Allowed product seams: campaign_manager T039/importer/shared formatter;
conversation_utils existing hub context; main existing hub DM note. No schema,
validator, provider, lock, archive, companion store or lifecycle changes.
Existing establish_hub creation action remains unchanged. All acceptance runs
must be sequential on isolated copies with real OpenAI, not model stubs.

Acceptance is NOT RUN yet. Runtime outcomes will be recorded with artifacts,
including FAILED/BLOCKED/NOT-REACHED. Plan agreement is not gameplay proof.

## C1-C3 implementation and focused checks

C1 commit2096a343: reviewed prompt exactly, original five goals/full source kept.
C2 commit3f9711a0: one no-fact-first field overlay, no validator change.
C3: one complete JSON formatter at both actual reader seams; surrounding
availability and other DM-note contents unchanged. Separate read-only simplifier
per slice found no removable machinery without losing approved behavior.

Local script local-data/322-primitives.py runs AST-extracted production parsing,
merge and formatting units, avoiding unrelated runtime/provider imports.128
checks PASSED: original captured invalid containers; historical scalar admission;
omitted/null/blank/empty-map preservation; explicit false/zero/empty-list updates;
input immutability/idempotence; complete untruncated formatting. This is pure
contract evidence, NOT simulated/live gameplay or proof of caller wiring.
py_compile all3 PASSED; diff whitespace PASSED. Pyflakes full report has inherited
unused/redefinition/missing-placeholder warnings but ZERO undefined names.
No incidental warning cleanup. Exactly2 production formatter calls found.

Native source/game copies use322-native-src-Elg2UF and322-game-IbP7La under C:/;
private evidence local-data/322-acceptance-oZxruI. Source and game setup must
finish and compare before any process launch. Existing311 source/game untouched.
New local storage approximately400MB, not another complete repository clone.

## C4 first real matched probe: FAILED semantic gate

Native Windows3.12.3, same authentic full T038 source, unchanged T039 profile
gpt-5.6-luna/none, serial calls via existing required child transport. Actual
response.model=gpt-5.6-luna in both results. Source export overlaid from current
worktree; source fixture untouched. Copies completed and party/sidecars compared
before execution. Artifacts under322-acceptance-oZxruI/C4-baseline andC4-candidate.

Baseline:12.156s, validatorFalse, reproduced array containers and object unlocks.
Candidate:11.843s, validatorTrue, but factual/preservation verdict FAILED.
Candidate hubs['Shadowfall Keep'].services=['possible stronghold'] converts a
prospective use into a current service. Existing importer would replace actual
services[rest,storage,sanctuary,information] with that proposal. Source does not
establish their removal/replacement. Unknown ownership was emitted as literal
'Not established'; an innkeeper was also treated as owner without ownership
evidence. Independent reviewer confirmed. No candidate export was imported into
the game; no A1/ordinary gameplay acceptance has begun. Not a PASS on JSON alone.

Failure classification: C1 agent instruction/compliance at the hub fact boundary,
not transport or new code guessing. Evaluating one narrow prompt refinement
under C4; no fabricated rejection/output and no prose-matching workaround.

## C4 single refinement and stop disposition

Seven generic instruction lines distinguish offered services from prospective
uses and explicit ownership from operating/staffing a location. Independent
source/simplifier review confirms this is within the approved C4 refinement,
not a new mechanism, identity rule, input source or model binding.

Real refined call:13.938s,response.model=gpt-5.6-luna,validatorTrue.
Hub-specific verdict PASSED: Shadowfall Keep no longer proposes services;
all four authentic services would survive. Unknown owners are omitted, Cira
is described as operator rather than owner. Existing metadata would survive.
This remains a real-model plus importer-primitive result, NOT persisted A1.

Overall factual C4 verdict FAILED: relationships['Lingering Spirit'] attributes
the unnamed cellar spirit's release to the named Withered Shrine guardian.
The supplied source distinguishes them; this is a T039 attribution error, not
the upstream T038 issue #318. No export was imported. Record filed under the
existing end-to-end identity pressure-test issue #326:
https://github.com/MoonlightByte/NeverEndingQuest/issues/326#issuecomment-5591360533
Exact request/result/capture:322-acceptance-oZxruI/C4-candidate-refined.
Result lines53-54; decoded sent source user-message lines5/19.

This is a different error from the first hub-services failure; it does not prove
that the hub fix failed twice. Nonetheless the second candidate is not globally
factually clean. No further prompt tuning, identity repair or model call is
performed; request owner disposition before moving past this failed probe.

## Consolidated current verdicts

| Gate | Verdict | Evidence and limits |
| --- | --- | --- |
| C0 isolated baseline/authority | PASSED | ac11ed0b, current main6d18d09b, D-322-1 |
| C1-C3 source implementation | PASSED | 2096a343,3f9711a0,b7227859 plus reviewed seven-line prompt refinement |
| Independent source audit | PASSED | Three-file byte-line/AST comparison, unchanged validator/transactions/other goals;2 live helper calls |
| Pure contracts | PASSED |132 WSL and132 native checks; independent reviewer44 additional cases; no gameplay simulation |
| Compile/undefined names/EOL | PASSED | all3 compile, zero undefined names, LF retained; inherited other lint warnings remain |
| C4 old prompt reproduction | PASSED repro |12.156s invalid actual output, retained validator firing shown |
| C4 initial candidate | FAILED |11.843s valid shape but unsupported hub services/owners |
| C4 refined hub contract | PASSED scoped |13.938s supported hubs and preservation semantics; actual import not run |
| C4 full factual output | FAILED |Distinct spirits conflated; #326 evidence above |
| A1 regeneration | NOT-REACHED |Held after C4 factual failure |
| A2 ordinary departure | NOT-REACHED |No gameplay acceptance started |
| A3 actual consumers/player claims | NOT-REACHED |Source wiring proven; actual DM request/narration not yet exercised |
| A4 full invalid/unlock polarity | NOT-REACHED |Captured invalid parser firing and empty unlock real output are proven; positive unlock/natural gameplay fallback not reached |
| A5 Save/Load/Quit | NOT-REACHED |No game process launched |
| A6 actual service/ownership change | NOT-REACHED |Pure replacement polarity only |
| Quiescence/preservation | PASSED scoped |All probe processes exited0; native owned Python scan empty; campaign/party/both sidecars byte-equal to original fixture |
| Postimplementation five-point audit | BLOCKED |Source section passed; live acceptance/owner judgment outstanding |

No merge/push/issue closure. Public issue updates contain observations only,
not private captures/keys. Original fixture unchanged. Three actual serial
OpenAI calls total; no phantom headless or native-gameplay PASS claimed.

## Owner disposition and acceptance resumed

2026-09-08 owner: "yes, keep it as a separte issue". D-322-3 codified in #193:
keep T039 attribution error under #326, continue narrow #322/#328 acceptance.
The failed full-factual probe remains FAILED; it is not a global quality PASS.
No attribution/identity repair, model change or further prompt tuning included.
Policy epoch20:18:57Z delta before resume was D-323-2 only (other agent's scope);
no #322 mechanics conflict. D-322-3 is this owner's subsequent scope disposition.
Native source campaign_manager SHAcb0a5ed1 matches the isolated worktree exactly.
A1 real maintenance regeneration is running on the copied fixture, not a
headless player command. Only one provider-backed operation active at a time.

### A1 completed maintenance run (preliminary artifact verification)

Native Windows real-OpenAI regeneration returned true in 48.875 seconds,
process exit0. Evidence: local-data/322-acceptance-oZxruI/A1-regeneration/.
summary-after.json clears export_failed; visitCount remains4. The eight
archived conversations and both companion-memory files have identical
before/after hashes in result.json. campaign-after.json retains the existing
Shadowfall Keep establishedDate, ownership, four services, connectedModules
and hubType while applying the exported description. Newly exported hubs
without ownership remain without ownership. This is maintenance execution,
not a headless gameplay PASS; independent artifact/factual review and the
remaining player-path arms are still outstanding.

## Continued acceptance: A1 PASSED, A3 FAILED (2026-09-08)

Independent A1 artifact audit verified captured T038 == saved summary, that
summary == T039 input, and parsed T039 == saved exportedData. Every supplied
field committed; omitted establishedDate/services/connectedModules survived.
All visit fields identical; all ten archive/memory hashes independently re-read
and matched. Selected profiles luna/none: T03840.434s (27989/4469 tokens),
T0398.197s (5000/885). Actual response.model unavailable in these captures.
A1 is PASSED maintenance API evidence, not gameplay.

Native actual headless A3 evidence:
local-data/322-acceptance-oZxruI/A2-A5-game-interactive/protocol.ndjson and
model_captures/T067.json,T065.json; game debug/api_captures/api_calls_master.jsonl
lines495-498. Native source hashes match all three scoped worktree files.
Original fixture remained untouched. First noninteractive relay could not accept
stdin, accepted no player command, and was stopped at its ready prompt with zero
children. Its evidence folder A2-A5-game is harness-only, not an acceptance PASS.
Interactive replacement executed exactly one recall input and then clean Quit.

Input: "Before we move, I take a moment to recall our bases and allies. What do
we actually own at Shadowfall Keep, what services are already available there,
and what help is available in Harrow's Hollow? I am only recalling what we know,
not claiming ownership of the village or changing anything."

Master495 T067 actual request messages2(system) and48(user DM-note) each contain
the complete formatter output including four saved services, ownership=party,
establishedDate and connectedModules. BOTH actual readers therefore reached.
Candidate names the four services. Master496 T065 rejects them:
"Invents confirmed Shadowfall Keep services such as rest, storage, sanctuary,
and information. The established record confirms only the deed, recovered
stores and relics, old chambers, and defenses; the keep is not yet a settled
refuge with verified functioning services. Revise the recollection to
distinguish known assets from unconfirmed facilities."

That validation request contains zero formatter markers and zero canonical
four-service JSON packet. Retry master497 removes the service claim; master498
accepts it. Delivered narrationseq579: "Shadowfall Keep is ours by deed, but it
remains a ruin, not a settled refuge. We have its recovered stores and relics,
along with old chambers and defenses we have not fully secured. I cannot swear
that any service there is ready." Full verbatim text retained in protocol.
This is an A3 player-truth FAIL, not a successful end-to-end hub fix.

One validation rejection/retry, two T067 + two T065 calls for this input.
Selected profiles: T067 luna/none8.780s and5.952s; T065 luna/low5.516s and6.072s.
Actual response.model unavailable; master model is routing metadata, not falsely
reported as provider-returned identity. Call completion relative to recorded
input: T06777.872s and175.082s; T065125.555s and208.476s (capture timestamps).
Delivery209.068s; next actionable promptseq664 at232.030s. No actions committed,
same TW05/time/HP. Quitseq666-669 accepted, player_exit, process exit0. Relay
exited0 and native owned-game Python scan empty (self excluded).

Acceptance stopped at this failed arm per the approved plan. A2 cross-module,
A5 full Save/Load and A6 real update remain NOT-REACHED; clean Quit alone is not
an A5 PASS. No product repair during acceptance. #326 identity finding remains
separate. Source/PX review of this newly observed validator-context gap requested.
No push, merge or closure.

Independent source audit confirms master495 candidate is exactly present in
validator496; its rejection causes the delivered denial, not merely coinciding
with it. main.py3118-3124 excludes system history and strips generated DM notes;
3275-3279 uses that selection;3469-3493 rebuilds validator evidence without hubs;
3566-3573 adds raw input/candidate;10384-10409 feeds rejection into correction.
The exclusion is mainline715732d55 and prefix mainline932aceb00, not newly added
by C1-C3. Smallest proposed scope amendment: a THIRD shared formatter consumer
at the canonical validator-evidence boundary. Preserve sanitized raw input,
all validation gates and producer/importer semantics. This exceeds the frozen
two-reader seam allowance and needs owner scope approval before implementation.

## C6 execution (2026-09-08; live acceptance in progress)

The preceding scope block is superseded by D-322-4 and reviewed execution
approval D-322-5 in live #193. Owner said "Approved" after nine clean same-SHA
reviews of plan a70581cbff8734323d9e8d20d3262f9d8321d3648bcef9068c0c2764e4006092.
The frozen plan records the approval gate historically; this entry closes it.
No push, merge or closure authorized.

Implementation: main.py +32/-0, direct read-only campaign hub evidence after
compression, before unchanged candidate assembly; one existing formatter.
No writer, recovery, global cache or new model call. Schematic updated.
Independent Custodian/simplifier PASSED: removing only added lines reproduces
HEAD main.py byte-for-byte; all gates/sanitizers/other readers are unchanged.
No equivalent simplification recommended. This is source evidence, not gameplay.

WSL and native Python312 compile PASSED; diff whitespace check PASSED.
13 AST-isolated JSON/evidence cases PASSED on both platforms (full long values,
unknown ownership, empty services, scalar history, absent file/map, error and
non-object root); these are pure primitives, not simulated player acceptance.
Script: local-data/322-c6-primitives.py. Native loaded main.py equals checkout:
aad11a313282c8eea148a2ab3ae685c8868e9f4080307a9d4a7a3b7bb10452eb.

Native real-OpenAI C6 rerun uses the same stopped copied game as original A3,
including its prior failed recall in accepted history (no history/state edits).
This is continuation, not a fresh pristine campaign; canonical campaign facts
remain the actual persisted source. Original FAILED evidence is retained.
New evidence: local-data/322-acceptance-oZxruI/C6-native-recall.

### C6 live result: consumer-delivery PASSED, full A3 factual PX FAILED

Master504 actual T067 system2/user52 and master505 T065 system29 contain the
same complete saved hub map; validator final raw/candidate pair remains exact.
T065 first attempt valid; previous false rejection of missing services is gone.
Selected profiles luna/none7.209s and luna/low5.842s; actual response.model absent.
Prompt/output tokens41671/367 and23332/192. Extra evidence236 o200k_base tokens;
total T065 prompt delta844 vs baseline also includes changed history/candidate.
Delivery114.212s, next prompt136.492s; no T065 rejection or correction. Thus the
separately required post-C6 rejection/correction control is NOT-REACHED.

Independent PX: 4/5 claims PASSED; services claim FAILED. Verbatim defect:
"restoration and further choices are still required before those services should
be treated as fully operational." All four services were named, not deleted;
no mechanical denial was observed. The recorded description requires stronghold
restoration, but does not condition its separately recorded services on that work.
No availability prerequisite was newly supplied by T039. That added relation is
not established by the stored facts. Do not relabel the whole arm PASSED because
the code boundary now works. No prompt/code repair during this failed acceptance.

Full verbatim narration, source evidence, exact rows, counts, provenance and
independent verdict: local-data/322-acceptance-oZxruI/C6-native-recall/VERDICT.md.
Campaign bytes unchanged, party unchanged, episode ledger unchanged; NPC sidecar
changed via ordinary beat work. Ancillary T107 fallback4 log rows and compression
BEAT_MALFORMED11 diagnostics retained; no all-pipeline-clean claim.
Quitseq562-565 completed, player_exit/process0; relay0; native owned-source/game
Python scan empty. A2/A5/A6 held at failed core gate. No push/merge/issue closure.

Postimplementation source audit and simplifier: independent Custodian and
Single-Path/No-Limits checks clean. Candidate raw FS1/limit/alternate-path scans
empty; exactly three formatter consumers. Pyflakes remains61 pre-existing
diagnostics with zero normalized delta and no undefined names. First comparison
failed solely because redefinition warning text embeds shifted line numbers;
normalizing those references shows identical diagnostic multisets. No clean-suite
claim and no unrelated cleanup. Review records are source-only, not live PASS.

## Follow-up after owner Continue (2026-09-08)

Read-only investigation confirms the service list survived unchanged and the
new complete context reached all three consumers. The current description says
potential stronghold requiring restoration; it does not explicitly establish a
dependency for the separate services list. The captured archive search found
establishHub instruction examples but not the original service-establishment
action. Therefore original service provenance beyond the authentic pre-existing
campaign record is unverified; no invented provenance or mechanical-refusal
claim is made. Existing establish_hub takes supplied services, defaulting to an
empty list, and does not derive a restoration restriction.

No product/prompt/state edits. Owner Continue permits further investigation:
one normal player clarification in the same game/history, per player-conduct
guideline3. It asks whether the narrated restriction is established or assumed,
without asserting a new service, changing state or deleting the failed history.
This is a separate correction-path observation, not a replacement clean A3 run
or a forced internal-validator rejection. Evidence C6-player-clarification.

Clarification OBSERVED correction-response PASSED independently: master511
T067 withdraws blanket restoration prerequisite,512 T065 accepts first attempt.
All four services retained. The model still qualifies current readiness as
unconfirmed, so original factual FAILED remains (no clean availability PASS).
Actual hub map at T067 system2/user56 and T065 system32. Selected luna/none
6.924s, luna/low4.636s; response.model unavailable. Delivery109.130s, prompt557
at131.223s. No gameplay actions, campaign bytes unchanged, same TW05/time/HP.
Quit562 player_exit, native and relay0; owned native Python scan empty.
Ancillary T107 fallback4 and compression BEAT_MALFORMED8 log rows retained.
Full verbatim evidence: C6-player-clarification/VERDICT.md.

Recommendation for owner: retain the proved evidence-supply fix and disposition
remaining readiness interpretation separately, rather than hard-code a semantic
service rule. This is a recommendation only: no acceptance gate waived, no new
public issue or code/prompt change. Held tests remain held pending disposition.

## Continued evidence collection (owner Cntinue, 2026-09-08)

Following the separate-readiness recommendation, owner directs continuation.
Readiness observation filed as #331, with factual FAIL and corrected-player
response both retained; this is not a blanket factual acceptance or ship ruling.
Resume previously held A2/A5 evidence collection on unchanged C6 source, same
copied native game/history. No code/prompt/state edits, no hard-coded services,
no retesting to replace the failed transcript. Evidence A2-A5-continuation.

### A2 and A5 PASSED; independent artifact verification complete

Real departure from Thornwood/TW05 to Keep_of_Doom/HH001/A05 completed in one
accepted travel turn. Actual T038 output equals saved summary and T039 input;
actual typed T039 equals saved exportedData, export_failed=false. Every supplied
field applied, omitted old hub fields lost0. Eight old archives unchanged.
Actual T108 adds one final episode; all150 old episodes exactly retained.
All three T013/T063/T064 narration calls complete. Arrivalseq529221.802s;
prompt613245.588s. Time07:51->11:51 once; same HP/XP/companions.

Post-travel real T067 and T065 requests carry full updated canonical hub map.
Save1000 completed; ordinary five-minute conversation changed party and NPC
sidecar. Real T065 rejection525 -> corrected T067526 -> valid527 -> prompt1364
at11:56. Exact rejected draft and feedback absent from durable history; exact
accepted response appears once. The rejection's PP005 component is a separately
observed missing-plot-evidence defect (#332), not a correct-judgment PASS.
No repair included. This firing path satisfies correction/history plumbing,
not a universally correct semantic validator or unrelated factual gate.

Load1386 selected_applied, status1387, restart1388, process0; campaign/party/
episode/NPC bytes each equal selected save. Relaunch A5-relaunch prompt214
returns saved11:51/A05, correct companions; welcome254, ready260, startupdone273.
Quit275-278 player_exit, process0, relay0, owned native Python scan empty.
Independent Custodian verified all above artifacts except controller orphan scan.

Full verbatim player text, call times/tokens, exact request keys/capture rows,
state comparisons, lifecycle counts and provenance: A2-A5-continuation/VERDICT.md.
All136 capture-record timings in call-timings.json; selected profiles identified,
actual response.model unavailable, not invented. T107 fallback/compression
diagnostics retained; no all-pipeline-clean claim. Native/WSL three-file compile
and whitespace check rerun PASSED (initial command used wrong conversation_utils
path; corrected to core/ai/conversation_utils.py, not a product failure).

## Consolidated scope/closure status

- A1 real maintenance regeneration: PASSED.
- A2 normal travel/export/preservation/memory/consumer: PASSED.
- A3 data preservation and three-consumer supply: PASSED; original narration
  readiness criterion FAILED/#331, player clarification-response PASSED only.
- Post-C6 rejection/correction/history isolation: PASSED mechanically, with
  #332 false-rejection attribution explicitly separated.
- A4 T039 shape probes: PASSED narrow shape after approved refinement;
  broader factual attribution FAILED/#326. Positive unlock/new natural invalid
  export fallback NOT-REACHED, no fabricated branch.
- A5 Save/turn/Load/relaunch/Quit: PASSED.
- A6 genuine service/ownership replacement: NOT-REACHED in actual play;
  explicit replacement/empty-list/false/zero primitive checks PASSED only.
- Pending-T039 cancellation and corruption live branches: NOT-REACHED.
- Source audit, simplifier, pure checks, compile and three-consumer invariants:
  PASSED. No new production change during continued acceptance.

Owner final disposition remains necessary for residual NOT-REACHED/factual
criteria and shipment. No overall PASS, push/merge or issue closure inferred.
#326/#331/#332 remain separate; no schema/readiness/plot/identity expansion.

## Owner acceptance and branch publication (2026-09-08)

The owner accepted the disclosed testing limits and authorized commit/push after
the narrow-scope completion summary. This closes the preceding owner-disposition
gate for publishing the issue branch. The recorded NOT-REACHED criteria remain
NOT-REACHED, and the separate #326/#331/#332 findings are not reclassified PASS.
Core implementation and native OpenAI acceptance are complete for this scope;
no claim of exhaustive coverage or resolution of those follow-ups is made.

Production commit addf3809 is unchanged after testing. This acceptance update is
documentation only. Publish fix/322-campaign-export-hubs; no merge into main or
issue closure is included in this operation.

# Issue 378: execute accepted storage/equipment steps in their listed order

Status: REVIEW CONVERGED (round2 eight-seat clean confirmation; final polish
under NEQ-REVIEW-11). Owner approved the presented
existing-referee safeguard approach for testing (D-378-1). No #378 implementation
until reviews clear; no merge/push authorization.
Date: 2026-09-12. Owner requested solving the retrieval overlap. This is an
explicit bounded extension alongside #374, not permission to repair inventory
generally. Present the converged plan before execution (NEQ-REVIEW-13).
Proposed runtime patch (NOT APPLIED): /mnt/c/agent-room-fleet-kit/local-data/
378-proposed-diff.patch. Normalized-text review artifact only; implementation
must preserve each original source region's line terminators.

## 1. Spec pin and authority

Live #193 v3.1, updatedAt2026-09-12T18:57:15Z (D-378-1 added). Read Part1, Part3/4, p4 and p6
NEQ-INV-01/02 (policy snapshot lines129-132), p10 NEQ-WEB-01, p11 routing,
p12 NEQ-SCHEMA-01/02 (161-164), p13 NEQ-ACCEPT-01..03/NEQ-TEST-01..02
(166-171). Snapshot /tmp/374-authorized-193.md matches current epoch; re-fetch
before implementation. Mainline schematics read: provider-routing.md,
travel-transitions.md, web-headless-surfaces.md. Current p6's missing T109 file
pointer is issue380, NOT permission to build a replacement resolver.

Dynamic Git evidence: isolated /home/loup/neq-worktrees/374-local-cache-contract,
branch plan/374-local-cache-contract, HEAD/origin-main observed8562e270; ancestry
must be rechecked at each gate. Revision is evidence only, never runtime authority.
Main remains untouched. Worktree holds two uncommitted #374 prompt edits
(+4/-4) and plan/acceptance docs. Preserve those four passages byte-for-byte;
#378 adds only the approved separate ordering paragraph to each validator prompt.
No schema, model-binding, item-writer or storage-manager edit.

README promises: Inventory & Storage; Player Storage System / Automatic Inventory
Management (lines713 and862-867). Preserve the player's item and accepted action,
not merely an attractive narration or a successful model call.

| Datum | Authority | Non-authority |
|---|---|---|
| Intent, proposed actions and sequence | Player input; T067 typed actions reviewed by existing T065 | Engine guessing from verbs/item names |
| Ownership/count/metadata | Character equipment and player_storage canonical records | Narration or future equip proposal |
| Retrieve completion | Existing manager result after existing writes/validation | Candidate saying item retrieved |
| Equip update | Existing T079 against freshly read committed sheet | Earlier pre-retrieval sheet |
| Supersession | Existing live scope/invocation claim | Exception text |
| Persistence | Existing writer/manager commits and SaveGameManager | New batch transaction/receipt (not proposed) |

Locks, queues, providers and public APIs unchanged. No provider wait moves under
a lock; continue using run_outside_response_fence. All supported entry points
share process_ai_response. Travel's earlier dedicated branches stay untouched.
No whole-turn atomicity or mid-call crash resumption claim: last clean Save is
the owner's accepted fallback. This plan creates no recovery store.

## 2. Forensics and challenged diagnosis

Private evidence /mnt/c/374-ev-gdyhCb/A and A3, native Windows, real OpenAI.
Full operator record local-data/374-native-acceptance-report.md; independent
forensics local-data/378-forensics-result.md. Both retrieve turns list
storageInteraction THEN updateCharacterInfo(equip) THEN updatePlot:
A/T067[6], A3/T067[1]. T065 A[5]/A3[0] approves this sequence.
Actual A protocol L2343 executes character update, L2493 storage; A3 L324/L481
same inversion. T079 sees no item and adds1; T049 retrieves1; manager merges to2.
Snapshots A prompt-2127->2643 and A3 prompt-110->603 prove conservation failure.
All19 T065 requests used candidate normalized hashfa47de4b; raw response.model
not captured (UNKNOWN), not inferred from selection labels.

Cause is CODE ordering at main.py:6539-6540/6588-6638, not evidence that the
referee must ban the legitimate retrieve-then-equip sequence. This supersedes the
earlier tentative '#378 addition-side wording gap' diagnosis in #374 acceptance;
the failure observations remain unchanged. No further #374 prompt tuning.

Lineage: a5703580f ('Fix concurrent character updates', 2025-07-26) replaced
the original ordered loop with a char-first split for ThreadPoolExecutor.
715732d55 removed concurrency, retaining sequential char-first residue. Current
goals are ordered state updates, stop-on-error, supersession and post-combat echo
filter, NOT executing equip before acquisition. Existing fee/combat/time prompt
contracts explicitly request the right array order. Code must honor that order.

Manager merge at storage_manager.py:174-186 is legitimate stack addition; writer
merge at updates/update_character_info.py:565-593 patches an existing exact-name
record but adds an absent one. Changing either would break real acquisitions.
The writer reloads canonical sheet at :1412 before building its request. With
retrieval first, it sees the transferred full record, not an absent item.

Failure seam: processor failure already returns needs_response at
action_handler.py:4419; manager failure :4435-4441 instead records an error then
returns continue at :4771. B/A6 protocol L1192 and unchanged prompt-1310 prove
this failure-to-continue path fired. Under corrected ordering it must not allow
the later equip to fabricate an item after a failed retrieval. Main already
handles needs_response at :6798-6831 by stopping siblings and requesting a fresh
reviewed DM response using updated history/current canonical context.

## 3. Smallest complete correction

C1: Restore ONE ordinary action loop in accepted array order. Remove char/other
partition and the separate character loop only. Reuse the existing richer
other-actions loop body as the sole loop over actions. Keep its failure/restore/
publication/levelup/needs_response/needs_update/exit/archive/supersession handling
unchanged. Do not add a storage-only execution branch or a dependency scheduler.

Before that loop, keep the existing post-combat echo predicate unchanged, but
filter into a replacement actions list: drop only predicate-matching character echoes,
retain EVERY other action in original relative order. Preserve existing notice,
history insertion, dropped count and telemetry. Empty response remains playable.
Retain received-action diagnostics; retire misleading split/char-first log lines.

C1b historical wording below is superseded by the reviewed bidirectional amendment
2026-09-12-issue-378-bidirectional-amendment.md (D-378-2); all other steps retained.
Original C1b: Add the following identical paragraph to full and compressed T065 prompts,
beside their top-level guidance and outside the existing #374 passages. Preserve
per-region line endings (LF additions, all unchanged bytes from the C0 copies).
Insertion targets: full line23 (after rule11), compressed line7 (after travel
grounding). Do not apply the zero-context review artifact with plain git apply;
use anchored edits and verify those positions, not an EOF append.
Exact wording is also local-data/378-prerequisite-paragraph.txt:

> ORDINARY ACTION ORDER: Check the proposed sequence before mutation; ordinary actions execute in their listed order, not all character updates first. Any state update for an already-resolved earlier consequence must precede createEncounter or exitGame, which end the current batch. Reject a candidate that places such a required update after them and request a corrected sequence without dropping the consequence. Do not invent an unresolved roll, choice, or prerequisite. A storageInteraction retrieval followed by updateCharacterInfo equipping the retrieved item is valid when the latter changes equipment state without duplicating the transferred item; equipping that item before retrieving it is invalid when it is not yet carried. Do not impose character-first order on unrelated actions. Existing dedicated travel, module-creation, and level-up contracts remain unchanged.

This mirrors the existing DM prerequisite rule into its existing reviewer; no
new call, hardcoded item, runtime prose parser, dependency scheduler or refusal
terminal. T065 rejection returns the existing corrected-candidate flow before
ordinary mutations. It is model enforcement, NOT a deterministic guarantee:
if both models accept a misordered terminal batch, later consequences can still
be lost. D-378-1 authorizes testing this approach, not claiming that risk solved
without evidence. Do not reinstate blanket character-first fallback.

Important corrected lineage: levelUp is intercepted at main.py:5478-5521 BEFORE
the ordinary loop and its siblings are ignored in either version. Contrary to
round1's hypothetical counterexample, #378 does not introduce that behavior.
Issue382 owns that existing pre-pass/prompt mismatch. createNewModule already
must be a singleton; restoreGame returns a RestoreRequest replacing the current
timeline, not a demand to mutate discarded state first. These remain unchanged.

C2: Complete the existing storage failure handback: unsuccessful manager result
must append the existing Storage Error note and return needs_response/needs_update,
like processor failure already does. Unexpected storage exception uses its
existing error note plus that same handback. Re-raise LiveProviderSuperseded and
InvocationSupersededError before the broad catch, using existing imports.
This only preserves exceptions that reach this branch. T049's inherited broad
catch can consume supersession first; that distinct defect remains issue375,
with the shared validation side tracked separately under issue324. Do not claim
this branch catch repairs cancellation throughout the storage call stack.
Missing character/description branches must likewise record their actual missing
input fact and hand back, not report continue and run later siblings. No new
error schema or fallback action. These are the same storage boundary's exit
polarities, not a new recovery subsystem. State already committed by earlier
actions remains; no rollback/replay of the whole accepted batch.

The handback note must make the execution fact explicit: this storage step
failed and later actions from this candidate have NOT executed. Request the
next step without replaying earlier completed actions; consult current state
before proposing mutations. Do not imply all earlier actions necessarily mutated
state or that an unexpected exception proves nothing committed. Model decides
the in-scene correction from actual state; code never narrates invented success
or infers equipment intent. Reuse existing reviewed follow-up; no per-turn model
call added on success. On failure, that existing T067 flow may make another call.

C3: Add a short shared ordinary-action-order subsection to existing
docs/architecture/web-headless-surfaces.md with exact changed seams and limits.
Also update docs/architecture/combat-typed-pipeline.md:44-52 only after the
prerequisite-order disposition below is implemented; its character-first statement
cannot remain after that mechanism is removed.
Update #374 acceptance's diagnosis by addendum only, keeping raw failures.

Runtime allowlist: main.py ordinary block, core/ai/action_handler.py storage
branch; prompts/validation/validation_prompt.txt and
prompts/validation/validation_prompt_compressed.txt (C1b paragraph only).
Documentation allowlist: this plan/acceptance and the existing surface
schematic and combat-typed-pipeline.md subsection. All other product files
frozen. #374's prior passages are frozen within the two now-allowed prompts. No
schema change, module/character name special case, new symbol/store/flag, numeric
bound, timer, retry policy, configuration edit, UI edit or new public API.

Rejected alternatives: stronger ban on equip alongside retrieve loses the
requested same-turn action; equip-only writer refusing all absent items breaks
acquisition; manager dedup breaks quantity stacking; prose-based dependency
guessing violates AP7; transaction framework/new microcall lacks necessity.

## 4. GL-1 behavioral contract

| Replaced area and origin | Goal | Disposition and proof |
|---|---|---|
| char-first split/loop, a5703580f then715732d55 | Once-only sequential mutations after concurrency removal | PRESERVED in one existing loop, original indexed actions once; A1/A2 and static AST |
| Incidental family-first ordering, same origin | Old concurrent batch admission | RETIRED proposal, owner gate D3781; replaces proven inversion, not desired inventory semantics |
| Character error/supersession catches,715732d55/4290e711/a51cab33 | Stop siblings, preserve authority, return truthful existing terminal | PRESERVED shared loop catches/results byte-identical; A2/A5 and static call/return trace |
| Postcombat filter,eb2ecd52f | Never replay committed combat mutations | PRESERVED unchanged predicate, all echo actions dropped regardless index, others kept; pure/static checks plus natural A6 |
| Storage failure continue exits,c88affc0 (2025-06-16); later path moves18e7052f/2c4721431/e1d27db4 | Preserve failure facts and keep play alive | PRESERVED fact note/playable fresh DM; RETIRED continuation into dependent siblings, A2 firing gate |
| #345 prerequisite writes before combat,45b99eac; #345 plan:190 and combat-typed-pipeline.md:47-48 | Apply resolved earlier consequences before combat, rather than lose them after a terminal action | PRESERVED goal via C1b existing reviewer check plus C1 ordered execution, subject to real A6 evidence; implicit character-first rescue RETIRED under D-378-1 trial. Model check is not deterministic equivalence; disclosed residual if T065 approves wrong order. |
| Fee/combat prerequisite/time ordering in mainline prompts | Fees and prerequisite state changes precede dependent work | PRESERVED accepted list order; A4 plus full/compact contract source checks |
| Existing richer action-loop special signals | Restore/exit/module/levelup/combat/history terminals stop later work | PRESERVED loop body unchanged except loop iterable/comment; static diff plus A5 |
| Received-action/debug split diagnostics | Observability | PRESERVED action enumeration and handler logs; RETIRED misleading grouping/timing prose, no gameplay consumer |

No retained game rule is implemented as a word list. No mutation on a rejected
candidate. Previously successful but incorrectly ordered arrays are not a new
compatibility promise; reviewers must produce concrete contrary contracts if any.
Round1 did produce a contrary contract: #345 used character-first dispatch as
its prerequisite-before-combat guarantee. The preceding general statement does
not waive that contract. A misordered [createEncounter, updateCharacterInfo]
can strand the update when combat returns its terminal signal. This sequence
is CODE-PROVEN possible, not observed in the 22 inspected accepted arrays.

## 5. Execution slices and development gates (after reviewed owner GO)

C0: Re-fetch epoch and ancestry, snapshot current dirty diff and per-file EOL,
confirm no overlap with another writer. Freeze known-good source/saved fixtures;
don't prune worktrees. Verify remaining GL1 branch origins, call families and
all updateCharacterInfo return types. Stop on actual unexpected contract.
C1/C1b/C2/C3 exactly as above, single writer. Fresh-context simplifier pass; then
independent actual-diff audit and both sentinels before real acceptance. No commit
or merge/push in this mandate. Candidate may stay uncommitted for owner review.

Gates: Python compile + pyflakes undefined names for both edited Python files;
ASCII additions, changed-region EOL comparison, untouched bytes preserved,
git diff --check (cr-at-eol), schema/model hashes unchanged; prompt delta exactly
C1b against frozen #374 copies /tmp/378-prefold-F0VkpM (hashes recorded). Pure AST/order/
serialization checks may cover the loop/filter/exit structure; no mocked game,
provider or narration, no synthetic integration test, no tracked test changes.
R3 expected sequences: retrieve->equip->plot; fee->retrieve->equip; two character
updates; noncharacter->character order; echoed character at any index dropped
only in actual postcombat mode; failed storage never reaches old sibling equip.
Static checks do not certify player outcome. No new global transaction claim.

## 6. Predeclared serial native acceptance

Use official Thornwood authentic saved cache at fixture A save_20260912_103037,
or clean B cache fixture from #374. Copy COMPLETE game; refresh prompts/schemas
from exported candidate; native-valid export without WSL .git pointer. Keep
originals unchanged. C:/Python312, configured real OpenAI and registry unchanged.
One operator, one input then read real response and choose next; no state edits,
fake responses, concurrent probes or infinite wording trials. No equipment
name special-casing. Stop new defects, file separately, do not repair mid-run.

| Arm | Required evidence and split verdicts |
|---|---|
| A1 primary retrieve+equip | Same real sentence as A3/001, actual T067/T065 pair contains storage then equip; show T049 commit BEFORE T079 call; T079 input now contains full transferred record. Total1->1, cache empty, equipped true, full prior metadata retained, next prompt and truthful narration. Pair absent = NOT-REACHED ordering, not PASS. |
| A2 failure gate | Ordinary request for an unavailable stored item plus intended use/equip. If manager refusal reached, failed storage handback prevents old sibling writer; fresh DM sees real failure/current state; no invented item, named next move, prompt. If models refuse before manager, model refusal PASS but manager handback NOT-REACHED. Exceptions/cancel only as naturally reached, no monkeypatch. |
| A3 roundtrip and second real item | Re-store/retrieve from same container, no duplicate-removal branch, quantity conserved. Use another already-owned eligible item through ordinary play if reachable; no invented fixture item. Verify generic implementation statically regardless. |
| A4 controls | Already-carried equip change; ordinary direct handoff with two updates; existing genuine fee->storage opportunity only if legal (otherwise NOT-REACHED). Correct route/order, no container invented for handoff; separate known writer failures. |
| A5 persistence and lifecycle | Supported Save, actual later turn, Load/relaunch -> item, cache and history equal saved state. Quit clean, zero orphans. Mid-call cancellation only naturally reachable; not claimed from static checks. |
| A6 combat filter | Natural postcombat response only if legal reachable without manufacturing combat; record whether character echo actually proposed and filtered. No forced echo; firing branch NOT-REACHED if absent. Static preservation is not a live PASS. |
| A6b prerequisite-order gate | On naturally grounded combat entry, capture resolved prerequisite actions and actual T065 disposition. Misordered candidate rejected then corrected before mutations = firing PASS; only correctly ordered candidates = compliant-path evidence, gate NOT-REACHED. Never invent trap/roll/state, edit captured candidate, or call a synthetic turn live acceptance. Retain unresolved-prerequisite wait control if naturally present. |

If T065 rejects a correctly ordered retrieve/equip pair on ordering grounds,
that is C1b over-rejection FAILED, not NOT-REACHED; quote every T065 verdict.
Evidence block per NEQ-EVIDENCE-04: every relevant T-ID, actual response.model or
UNKNOWN, duration relative to input and capture index/line; parsed payload keys;
full narration verbatim beside state; lifecycle/error/degrade counts with scans;
every accepted action array in order, including any character update following
a terminal action. A1 metadata is compared against the selected cache's actual
pre-run record, not an older pre-loss record. Prefer A's saved fixture for the
matched A3 pre-fix control; record its already-stale AC18, which is not evidence
of successful equipment application. A2 must quote both any premature success
narration and the later corrective narration: this repair does not move the
initial narration after commits (#364/#360). A6 should attempt one ordinary
postcombat turn if legally reachable; no synthetic echo or automatic PASS.
fixture provenance. Record loaded prompt disk+normalized hashes and compare to
candidate; full prompt live NOT-REACHED if compression selects compact (no mode
toggle). Before/after state diffs include every nonempty->empty and item quantity.
Full browser and crash atomicity untested, not implied by native headless.
Independent PX reviewer checks at least five concrete narrative claims on disk.
Acceptance failures are never erased by later player corrections. #374 cache
deposit remains a regression requirement; verify original ordinary phrasing once.

## 7. Review protocol and gates

Run the plan review protocol. FULL: deletion/ordering replacement/GL1 and shared
entry point. Separate parallel blind Claude Code Opus5 medium seats: Architecture,
Fail-Forward, Acceptance, Consumer/Compat, Legacy/GL1, Player Experience, No-Limits,
Single-Path. No new mechanism/public symbol, so Leanness DA not triggered unless
review adds one; Custodian owns its coverage/net-negative tests. Each reviewer
receives this whole plan and ledger, current policy, own lane and write-none
contract; R1-R15 apply, no author reasoning or other draft included. Controller
single-writes corrections. Same-SHA convergence then clean confirmation per R11;
only purely documentary polish qualifies for its exception.

Sentinels paste actual scan output of candidate diff and touched files; before
code use the explicit proposed patch artifact plus frozen #374 diff, labelled
PROPOSED, then mandatory actual diff at execution gate. Inherited out-of-block
hits are enumerated with lineage and existing issues, not silently approved or
fixed. FULL never downgrades. Review agreement is not execution or merge GO.

## Tracked follow-ups

#377 create_storage ignoring supplied items; #379 T051 value0 AC interpretation;
#371 T053 validation; #358 exact ammunition identity; #370 item identity;
#364/#360 broader failure narration; #368 handoff ownership; #375 T049 ordinary
completed-invalid bound; #376 obsolete full-prompt action aliases; #324/#276/
#262 inherited caps/retry exits outside this correction; #380 stale p6 T109
pointer. No repair absorbed. Only #378 observed ordering plus same storage
failure boundary belong here. Schema/database changes are not authorized.
Issue381 owns the direct versus transition-staged storage-path audit, including
authentic old-checkpoint reachability before any proposed consolidation.
Issue293/D-8 (and interim #284/D-VS-7) owns the inherited generic provider-failure
stop reachable in the fresh-DM follow-up, not a new bound introduced here.
Issue382 owns the inherited levelUp pre-pass ignoring all siblings regardless
of order. Not introduced by C1; no specialist or progression repair included.

## Resolution ledger

| ID | Disposition | Evidence |
|---|---|---|
| F1 runtime ordering, not blanket equip prohibition | task-C1 | A/A3 accepted arrays versus actual execution |
| F2 failed storage continues to dependent work | task-C2 | B/A6 actual continue + source return chain |
| F3 goals of old split/postcombat/terminal handling | task-C0/C1 | a5703580f,715732d55,eb2ecd52f, shared loop source |
| F4 missing p6 T109 paths | issue-#380 | both absent on current main; no replacement invented |
| F5 earlier wording-gap diagnosis | fixed-inline | superseded in section2, preserve observation |
| D3781 owner execution after presented safeguard architecture | task-C1/C1b/C2/C3 | Owner approved trial, live193 D-378-1; complete confirmation then implement/test only, no shipment |

### Round1 dispositions and next gate

All eight round1 blind reports are saved verbatim at local-data/378-r1-<seat>.md.
Seven seats had no blockers; Legacy's contract block is folded as C1b with owner
trial authority. Round2 must independently verify that fold and the full ledger;
the proposed runtime artifact remains unapplied until convergence.

| Review finding | Disposition | Resolution/check |
|---|---|---|
| Legacy F1 / Architecture F-C1, #345 safeguard and stale schematic | task-C1b/C3 | D-378-1 approves existing T065 prerequisite-order trial; exact clause above. Trace terminals and dedicated paths; same-SHA confirmation required; no deterministic guarantee claimed. |
| Legacy F2 storage origin | fixed-inline | c88affc0 is original implementation; later commits moved paths |
| Legacy F3 / Architecture FYI all echoes removed | fyi | Empty filtered list may signal Ready earlier; retain no-action behavior, document static result |
| Acceptance F1 / Player FYI fixture metadata and AC | fixed-inline | Compare current cache record; starting AC18 is nondiscriminating; matched A3 control preferred |
| Acceptance F2 earlier committed fee not replayed | task-C2 | Proposed artifact revised to caution against repeating earlier completed actions; consult current state, no invented whole-batch outcome |
| Acceptance F3 natural combat filter / F4 terminal arrays | fixed-inline | Attempt legal A6, log every accepted array, honest NOT-REACHED |
| Consumer rest/time order | task-C1 gate | Verify ordered updateTime then rest update statically; live only if naturally reachable |
| FailForward F-FF-1 / Consumer inherited inner supersession catch | issue-#375/#324 | Qualify branch-level rethrow; do not claim whole-stack cancellation repaired |
| FailForward F-FF-2 inherited T049 count | issue-#375 | Existing failure handback continues; no unrelated retry repair |
| NoLimits inherited generic provider stop / status clips | issue-#293/D-8/#284 and #262/#276 | Enumerated, unchanged; no new limits |
| SinglePath direct/staged implementation audit | issue-#381 | Separate reachability and compatibility work, not automatic runtime merger |
| Sentinels no newly introduced bounds or duplicate runtimes | fyi | Proposed artifact scan only; actual-diff gate mandatory after authorization |

Round2: all eight seats confirm zero in-scope blocking findings on plan03dfa664.
Raw reports: local-data/378-r2-<seat>.md. Acceptance F-ACC-5 (over-rejection is
FAIL, not unreached) and Architecture/Legacy artifact-position notes are
fixed-inline plan-polish only: no change to code steps, task semantics or test
inputs. All code-class round1 folds have R2 re-verification. NEQ-REVIEW-11's
plan-polish termination exception applies; no ceremonial additional dispatch.

The T065 check is owner-approved for trial, not yet applied, and not proof of
deterministic prevention. All prior failed and unreached evidence is retained.

No product code changed by writing this plan. #374's original four passages
remain intact. D-378-1 authorizes the narrow structural correction, C1b and
serial testing after confirmation, not merging into main or unrelated repairs.

## Execution checkpoint: 2026-09-12 FAILED TRIAL

The preceding plan text was implemented and tested at SHA 37bd2df76d2e4fb542bde6a06ccf58beb976490b63eab9e98ac23eb306f281c7.
Its earlier not-yet-applied statements describe the planning checkpoint, not the
current working tree. A1 retrieval passed, but A3 storing then unequipping
duplicated the item. Acceptance stopped and the copied game quit cleanly.
See 2026-09-12-issue-378-retrieve-equip-order-acceptance.md for the failed approach,
evidence and proposed symmetric prerequisite correction. No further correction
was applied. Status: FAILED / NOT MERGEABLE; outstanding arms remain unproven.

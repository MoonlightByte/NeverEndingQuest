# Issue 311: module-final companion memory repair plan

Status: EXECUTION APPROVED by owner: "execute this plan. sounds good".
Original review and clean confirmation passed before approval. Task-4 is a
substantive acceptance-driven amendment: owner accepted its preservation-first
compatibility choice on 2026-09-07. Full amended-plan review and clean
confirmation PASSED all nine seats on substantive SHA 5cc5b4fde08cb4f7c89e7dbe128ca4d8f2f0213557007f1cfdeab9a6c3dc98ae.
Task-4 and task-2 FF-1 execution APPROVED after presentation, owner:
"aoprvoed continue" (2026-09-07). Implementation and testing are underway.
This status stamp changes no reviewed contract.
Merge, push and issue closure remain separately gated.

## Authority and evidence pin

Owner requested this issue and a full #193 review of the plan. Policy read live:
#193 v3.1, refreshed updatedAt 2026-09-07T18:48:35Z with D-311-2
codified in Part 5. Issue #293 read for open rulings.
Inspection baseline main 99876535b4c9d24c29384236d52d03bfddc621be, captured
2026-09-07 UTC; this revision is evidence, never runtime authority. Refresh
main ancestry and policy epoch before implementation and shipment.
Planning branch docs/311-module-final-memory-plan, isolated WSL worktree
/home/loup/neq-worktrees/311-module-final-memory (D-WT-1).
Execution branch: fix/311-module-final-memory in that same isolated worktree.
Original execution-start policy epoch was 2026-09-07T04:50:09Z; origin/main
is unchanged from this evidence pin. The amendment uses the refreshed epoch.

Applicable doctrine: Part 2 p7 NEQ-NPC-01/02 (grounded attributed recall),
p8 NEQ-WORLD-03/04 (module bubbles and player-data preservation), p9
NEQ-SAVE-01/02 (controls and snapshots), p10 NEQ-WEB-01/03 (no provider wait
under lifecycle locks, honest progress), p11 NEQ-PROVIDER-01/02 (registry and
observational telemetry), p12 NEQ-SCHEMA-01/02 (frozen schemas/preservation),
p13 NEQ-ACCEPT-01..03 and NEQ-TEST-02. Part 5 Fork-3, D-VS-7/13/14,
D-248-1/2 and NEQ-LEDGER-06/08/09 apply without expanding their scope.
README promises: Relationship Tracking at line237, NPC Memory at419,
Cross-Module Memory at680, Persistent Companions at851.

Read schematics: module-lifecycle, companion-memory, npc-voice-ooc,
provider-routing, save-load-reset-lifecycle. Their historical line pins and
pending-acceptance statements are orientation, not current proof.

## 1. Root cause and rejected shortcuts

CODE-PROVEN, not a newly observed live incident: CampaignManager's
_commit_module_summary_locked (core/managers/campaign_manager.py:3386) reads
undefined party_tracker_data at3612/3619 and conversation_history at3616.
The except Exception: pass at3623 hides NameError before T108 dispatch.
Command: python3 -m pyflakes core/managers/campaign_manager.py. Exact output:

```text
core/managers/campaign_manager.py:3612:46: undefined name 'party_tracker_data'
core/managers/campaign_manager.py:3616:17: undefined name 'conversation_history'
core/managers/campaign_manager.py:3619:30: undefined name 'party_tracker_data'
```

The caller at3300-3336 holds party-transition, per-module completion, and
campaign locks. The comment claiming capture is outside locks is false.
Simply supplying variables here would introduce a provider-under-lock failure.
Summary regeneration also calls this helper at4324; its archived history plus
live root tracker is not an authoritative historical final-location snapshot.

Lineage: 1adc947dd (always-live T5, 2026-08-22) supplies the unconditional
missing-input block; 4797bfb9a (three NPC review fixes) supplies its post-commit
placement intent and swallow. Both predate #248. 715732d55 owns the surrounding
commit-marker sequence; b0fab5775 preserves exact work expectations;
d61f20d31 adds typed cancellation propagation. Keep those goals.

Additional code-proven entrant: complete_module borrows get_live_provider_scope
(campaign_manager:394-416). Accepted Save executes under a control scope with
controls_open=False (live_provider_call:593-615). open_advisory_scopes:243-245
accepts only current ordinary/welcome identity, and registration:185-187 rejects
closed controls. Merely threading an advisory argument would miss Save.

Rejected: module globals/live destination reads; provider call under commit locks;
new memory store/outbox/receipt/schema; whole-history or main-DM regeneration;
fire-and-forget module-final capture; changing model/effort; new transport policy.
No narration prompt tuning or manually authored memory facts.

## 2. Proposed smallest complete change

Keep one synchronous module-final consolidation, AFTER existing summary commit
returns and releases its locks, BEFORE completing the current completion flight.
The model still interprets the existing full-fidelity final scene through T108;
code supplies the correct frozen origin inputs, lifetime, identity and persistence.

Flow:

```text
ready completion intent -> existing frozen origin party/history
 -> existing archive/T038/T039 -> existing locked campaign commit
 -> release all completion/party/campaign locks
 -> existing completion-owned T108 child -> existing episode/POV stores
 -> finish child -> resolve completion flight -> existing intent cleanup
```

### task-1: place the call at the public completion owner

Remove only the faulty consolidation block from _commit_module_summary_locked.
In complete_module's leader path, after _complete_module_once returns (outside
its ExitStack) and before completion.set_result, call consolidation with copies
of existing party_snapshot/history_snapshot, explicit origin module_name and
ModulePathManager(module_name), and player name from that same snapshot.
No new persisted data. Only the leader performs the capture; joined followers
receive the leader result under their existing epoch/receipt revalidation.

This placement includes same-ID receipt/recovery returns: the still-ready
staged intent supplies the same origin snapshot on restart, so a crash after
summary commit but before capture can retry the missing episode. Successful
capture precedes normal intent removal. A direct complete_module caller owns
the meaning of its explicit snapshot as today; do not substitute current live
destination fields. No new recovery sweep of historical completed modules.

Regeneration remains summary-only: remove the accidentally shared broken capture
from that path, do not create a new final-location memory from its live tracker.
It retains visit counts/archive/exports and existing success/failure behavior.
If historical-memory repair is requested later, use its own scoped proposal,
not a new archive reconstruction policy hidden in this repair.

### task-2: use the existing completion-owned advisory lifetime

Use get_live_provider_scope (the existing completion decorator guarantees an
owner) and open_advisory_scopes with completion_required=True for one T108 child.
Pass optional advisory_scope through consolidate_module_episodes to the existing
capture_location_episode/extract_episode chain. Finish that child in finally,
after persistence or discard, before completing the flight/control callback.
No executor or thread is introduced. The existing provider child does the I/O.

Adapt the existing two registration gates to admit the EXACT current
_executing_control_scope identity as well as existing ordinary/welcome owners.
Closed external controls remain closed: the exception permits an internal child
of the currently executing accepted operation, not another player command or a
stale arbitrary scope. Supersession remains rejection at both gates. Do not
change get_live_turn_scope, global registration, Save ordering, or drain behavior.
Only synchronous #311 code selects a control scope for this child; enumerate
all existing registration callers before editing. Children finish before Save
callback return; no async control child is introduced.

Genuine supersession propagates unchanged. If registration cannot admit an
otherwise expected live owner, record a loud health failure and preserve the
committed module; never fall into unscoped provider execution. D-VS-13's existing
late unscoped async capture remains unchanged; D-VS-13a is not decided here.
Recheck existing scope and completion epoch immediately before T108, after its
return and before entering the episode persistence chain. No provider wait under
any party/campaign/episode/relationship lock; do not hold a scope lock around
provider or persistence waits. Lifecycle controls still quiesce the owning game
thread and registered child before replacing files.

FF-1 amendment (source-proven, not an observed live incident): an unavailable
epoch read at a new synchronous check currently enters the broad advisory catch;
completion can then clear its ready intent without final memory. Temporary busy
authority is not completed-invalid extraction. Add one private
_wait_for_live_authority in existing live_provider_call.py: loop on the existing
nonwaiting _check_live_authority; on OSError use existing _interruptible_wait
with its existing 0.25-second poll cadence and truthful memory progress, then
retry. No attempt cap or terminal deadline. Typed supersession escapes unchanged.
Do not change _check_live_authority, current(), or any provider-poll callback:
those observations must remain nonwaiting so an active provider child can reap.

Replace only the six new #311 synchronous checks: campaign_manager3047/3062
and episode_capture202/208/543/574. All run outside store/party/campaign locks
and outside an active provider request. The post-extraction check retains the
local typed result while waiting; it does not discard or re-extract it. Keep
the registered child owned until persistence/discard and finally finish it.
Completed-invalid extraction and invalid visit metadata still use existing loud
advisory handling; an unreadable authority observation is neither of those.
The private helper's two-file caller family and FF-1 are its AP-4 warrant; no
new public API, store, lock, worker, policy or unrelated retry refactor.

### task-3: preserve idempotency and make failure observable

The original close-(N+1) module-final identity is superseded by task-4 below:
use origin module/location plus the returned committed visit's module-visit-N
boundary. stable_episode_id at episode_store:51 continues deriving UUID5 from
module|location|boundary values, not prose. Ordinary location boundaries stay
unchanged; module-final capture has one identity path, not a legacy fallback.
Before another extraction on replay, query that exact existing coordinate using
the existing store read API. If a valid canonical record exists, preserve it:
skip T108 and canonical rewriting, but finish its deterministic POV/baseline
projection before returning its ID. A process can stop after canonical commit
but before any or all companion projections; canonical existence alone is not
proof that those separate writes finished. Missing record uses the existing
T108 -> canonical commit -> same POV/baseline projection path.

Extract the existing projection body (_commit_and_overlay:256-271) into ONE
private shared helper used by new canonical commits and this module-final replay.
Derive from the stored canonical episode, never a fresh model paraphrase. Reuse
upsert_pov_episodes and reinforce_baseline_from_pov: episode-ID keyed writes
and the existing persona-baseline-plus-pinned-memory calculation, not additive
replay increments. Eligible POVs are only the NPC-attributed facts actually
returned by T108; a witness without such facts need not have a POV row. Complete
unchanged projections are no-ops; unrelated episodes/persona/relationships stay
intact. Do not treat an idempotent False return as a failed write. No new marker,
recovery sweep, cross-file transaction or retained transient model response.
The store remains final authority; no new write format or invented facts.

No witnesses/empty final segment are normal no-work results, not failures or
evidence of a T108 pass. Failed extraction/commit and failed POV derivation must
be reported separately through existing store-health telemetry and WARN-or-higher
logging. Replace DEBUG-only swallows along this specific chain with existing
health reporting; maintain typed cancellation propagation and ordinary advisory
failure semantics. Do not claim a canonical write proves a successful overlay.
Existing canonical success plus a later overlay failure remains independently
reported, not erased or treated as an atomic cross-file transaction.

Transport transient failure uses existing completion-required reap/reissue;
no new timeout, retry counter or skip rule. Completed invalid/deterministic
advisory failure uses the existing one-beat Fork-3 handling, loudly, without
turning committed module completion into failure. No claim of exactly-once
billing across crashes. Source history/archive remain intact for later recovery.

### task-4: distinguish another module visit from replay

Observed at d11bfec5 in native acceptance: real receipt completion_id
6d6aa3d2-4811-468a-818c-17fe4f6ad3f4 has committed visitCount2; its frozen
Thornwood/RO01 history has16 location markers. Existing prior-visit canonical
f2eba100-9aef-5c37-8b45-079f9d034e11 already occupies close-17. Real restart
drains that new completion without T108, leaving ledger143 unchanged. Evidence:
/mnt/c/agent-room-fleet-kit/local-data/311-native-crash-before-memory/cut and
/mnt/c/agent-room-fleet-kit/local-data/311-native-crash-resume. Independent
source/compat review confirmed the collision. This is in-scope memory identity,
not an archive/compaction rewrite. The original A2 cut is not a memory PASS.

Pass result['visitCount'] from _complete_module_once into consolidation as a
required keyword module_visit. Validate a positive integer (not bool); form
boundary 'module-visit-%d'. No upper limit, truncation or content-derived ID.
Bad/missing visit metadata uses existing loud advisory failure handling and
preserves the committed module, never guesses a close-N identity or runs an
unscoped extra provider call. No new recovery gate on the player path.

The existing visit assignment occurs under completion/campaign locks at
campaign_manager3356-3362. Receipt.result preserves the original committed
visit; same-ID replay returns that result3182. Direct completion_id=None and
overlap callers also receive their committed result3232. Use that return value,
never a later read of the latest summary. No new lock, receipt, schema, store,
model, prompt, worker or provider policy. The one production consolidation
caller is campaign_manager3055; both staged and direct complete_module entrants
flow there. Optional old close-N runtime behavior is not retained.

D-311-2 ACCEPTED by owner ('accepted', 2026-09-07): preserve all old close-N
episodes untouched. Do not rename/delete them, guess their visit from content,
or use old-coordinate existence as replay authority. An interrupted old-build
completion may acquire one additional episode under the new visit coordinate;
owner accepted this preservation-first compatibility tradeoff. Thereafter
replay of that committed visit reuses the new coordinate. Do not claim an
automatic migration or universal absence of old records. The authentic baseline
fixture contains zero module_consolidation records; candidate-generated test
records do exist. All existing memories and their links remain readable.

Schema remains frozen: boundaryTurnId is already a string; existing retrieval
grain follows derivedFrom=module_consolidation independently of boundary spelling.
Change only campaign_manager.py and episode_capture.py plus scoped docs. Remove
the old count helper only if a whole-repo caller search proves it is used solely
by this replaced module-final coordinate; keep location/combat/backfill logic.
This step replaces the task-3 identity assumption, not its shared projection,
scope/epoch, no-provider-under-lock or canonical-preservation requirements.

## 3. Authority and end-state contract

| Datum | Authority | Forbidden substitute |
|---|---|---|
| Final scene/roster/time | Frozen origin party/history, durable staged intent on resume | Current destination tracker, narration guess |
| Completion result | Existing committed summary/campaign/receipt | Episode success flag |
| Episode content | Typed T108 extraction grounded in actual scene | Code prose parsing for story meaning |
| Module-final episode identity | Origin module/location and returned committed result.visitCount | Conversation marker count, latest live visit, text hash, new receipt |
| POV/relationship | Existing per-NPC store mutation | Empty defaults or fabricated recollections |
| Cancellation | Existing owner scope + campaign epoch | Elapsed time or missing capture log |

Success: module unchanged, final eligible episode and POV persisted once, flight
returns normally; later recall consumes it. Existing canonical replay: no rewrite.
No-work: module completes, no made-up episode. Advisory completed failure: module
completes with loud diagnostic/telemetry, no claimed memory success. Supersession:
child reaped, typed unwind, no stale publication after replacement; prior module
commit remains valid. Process loss: existing intent/receipts resume; no promise
to preserve transient model results, and no new crash-save state.

Lock order remains party -> per-module completion -> campaign for commit.
Provider work holds none of those. Episode/relationship locks remain separate
and sequential as now. Registered-child lifetime spans store work; quiescence
is not identical to provider completion. Concurrent external unmanaged writers
and unscoped late capture are not newly brought under this operation's authority.

## 4. GL-1 behavioral contract

| Removed/replaced behavior | Origin | Goal | Disposition / proof |
|---|---|---|---|
| Faulty locked capture block | 4797bfb9a / 1adc947dd | Final location remembered after durable completion | PRESERVED task-1, A1/A2 |
| Typed cancellation catch at old call site | d61f20d31 #248 | No stale work after accepted controls | PRESERVED task-2 at new site, A3 |
| Silent except/pass and DEBUG capture failures | 4797bfb9a / adf280a8d | Memory failure must not fail module | PRESERVED nonfatal; visibility restored task-3, A4 |
| Incidental invocation from regeneration | Shared commit block above | Do not invent old-module facts from live destination | RETIRED as unreachable missing-input side effect under #311 proposal; owner execution gate required |
| Ordinary/welcome registration identity rule | c1ede401d registration / 5819974a8 parent admission | Only owning workflow registers a child | PRESERVED exact identity; add current accepted-control entrant task-2, D2/A3 |
| Re-extract final canonical episode on replay | adf280a8d projection sequence / existing coordinate API | Stable memory with no duplicate ordinal, full eligible POV and baseline | PRESERVED through shared projection of stored canonical record, task-3, A2/D1 |
| Marker-count module-final identity | b164fc31, activated and replay-checked by a1e022fe/d11bfec5 | Same completion idempotent; distinct visit remembered | PRESERVED by task-4 committed visit identity; A2b/D4 |
| Old close-N canonical/POV records | existing player data | Never erase/rewrite memories | PRESERVED untouched; D-311-2 accepted possible one-time duplicate on old-build interrupted completion |

No unrelated branch, fallback, bound, schema, default or persisted field is retired.

## 5. Scope and mechanism budget

Product allowlist (proposed, no edits yet):
1. core/managers/campaign_manager.py: call relocation and owned lifetime only.
2. core/npc/episode_capture.py: optional scope threading, module-final replay
   lookup, shared private projection helper, boundary authority check, and
   failure reporting on the used chain.
3. core/npc/episode_extraction.py: typed failure visibility only, no prompt/schema.
4. utils/capture/live_provider_call.py: exact executing-control child admission
   at the two existing gates, plus the private synchronous authority-wait helper
   for FF-1. Transport polling and external controls remain unchanged.
Docs: module-lifecycle.md, companion-memory.md, provider-routing.md (changed
seams only), this plan and evidence report. Update false unlocked/working-final
capture description and #248's historical #311 pointer with current evidence.
Earlier #248 audits remain historical evidence, not competing plans to overwrite.

No new public helper expected; optional existing-API argument only. If factoring
is needed, a private helper requires its observed #311 warrant and callers in
the same slice. No new store/format/worker/policy/flag. No schema changes.
Schema-Freeze is verification-only: authentic sidecars validate unchanged.
No model binding/effort changes: existing T108 OpenAI luna/low; all other
configured-provider semantics stay inherited. WSL OpenAI primary acceptance;
native Windows real-provider corroboration required before end-user/ship claims.

## 6. Implementation sequence after owner execution approval

C0: re-read live policy, branch/ancestry and exact reviewed SHA; freeze real
sidecar/schema/ABI/line-ending inventory; baseline compile/undefined-name gate;
record expected three undefined references only. Commit approved baseline docs.
C1: task-1 + task-2 in one coherent integration slice (do not activate a
lock-held or unscoped intermediate). Local static/scope primitive checks;
independent diff review; simplifier; commit. No live acceptance yet.
C2: task-3, docs and exact before/after field preservation gates; independent
review and simplifier; commit. No unrelated repair or tracked tests.
C2b: task-4 and task-2 FF-1 after amended-plan review/presentation approval; source/primitive
gates, independent diff review and simplifier, one correction commit. Update the
same three schematics' #311 delta paragraphs. Original review evidence stays
historical, not approval for an unreviewed identity change.
C3: sequential real acceptance below, one game operation at a time; independent
Player-Experience review against disk; final non-author five-point audit and
both sentinel scans. Present owner report; no automatic merge/push/issue closure.

## 7. Acceptance designed before code

Reuse a small copied official Keep_of_Doom two-companion saved campaign from
existing local evidence, then travel legally to installed The_Thornwood_Watch.
Record exact source fixture and byte-identical pre-run state before execution;
do not modify characters, membership, history, episode ledgers, or plot state.
Refresh static prompts from the tested checkout (including actual hashes).
If no such fixture is usable, recruit through actual play; do not fabricate one.
No new large source clone; same isolated worktree plus one active game copy.

| Arm | Real operation and required evidence |
|---|---|
| A1 | In the final origin location, have a genuine companion exchange; then one legal cross-module move. Capture origin scene/roster, actual T108 request/response, existing T038/T039 and T013/T063/T064, module commit chronology, one final coordinate and per-NPC POV. Inspect actual T112/T105/T067 request on a later natural recall question and verbatim grounded DM answer. Absent-mentioned NPC gets no witness/fact. |
| A2 | Real process interruption around committed module/before intent cleanup; restart same game path, no fake marker. Missing episode must be captured from retained origin inputs. Separately reach canonical-present/eligible-POV-missing (before first projection or between companions): canonical bytes/ordinal stay unchanged, zero new T108, missing eligible POV and baseline complete before intent cleanup. Already-complete replay is the no-change control. Prove proactive POV injection and targeted canonical recall independently from their actual requests; one cannot substitute for the other. Visit/archive remain unchanged. Every unreached cut is NOT-REACHED, not pass. |
| A2b | Real repeated visits to the same module/location with unchanged location-marker count: each committed visit adds its own final episode, old canonical/POV remain unchanged. Replay the same visit using actual interruption/restart: same episode/ordinal, no extra archive/visit. Old-coordinate records remain readable and unchanged under D-311-2, never used to suppress the new visit. |
| A3 | Real Load/Reset/Quit during actual module-final T108, one operation per fresh lineage; prove task identity/child reap, truthful controls and no stale mutation after replacement. Separately accepted queued Save settling completion: child belongs to that exact executing control, no deadlock, saved sidecar equals committed safe-boundary state. If no real Save entrant reaches this seam, label NOT-REACHED and request owner disposition. |
| A4 | No-companion normal completion (no T108 needed), same-module location-close and ordinary combat memory unaffected, summary regeneration does not increment visits/archive or extract a false final memory. Natural completed-invalid/provider error/store failure: record exact typed disposition and subsequent playable state if reached; never fake it. |
| A5 | Real Save -> later turn -> Load preserves canonical episode/POV and grounding; capture hashes immediately after Save and after later turn before Load. Fresh no-pending startup and ordinary next turn still work; scope quiescent and zero orphan children at end. |

All acceptance sequential, real OpenAI as configured; native Windows arm uses
the same source revision and fresh prompt bytes, with binary-pipe/path/lock
checks. Do not conflate Linux pass with native proof. No local-model runs.
No mocks, monkeypatching, fabricated outputs, gameplay edits or new test hooks.
Dedicated primitive-only D1: coordinate parsing/existing-record preservation,
canonical-present/eligible-POV-missing repair and complete replay no-change using
the real persistence primitives with specified data (not a fake model run);
D2: exact active/welcome/control identity registration and sealed/stale rejection,
completion_required flag, child finally/quiescence (no fake model response);
D3: schema/read-write primitives with independently specified fixture values.
D4: committed-visit identity primitives: visits1/2 differ; identical visit reuses;
positive-int versus missing/bool/invalid metadata; existing old-coordinate record
unchanged; direct caller uses returned visit. No fake model responses or mocked
gameplay; source tracing and primitives do not substitute for live A2b.
These are aids, never live acceptance substitutes. Tests ignored/local only.

D5 for FF-1: native filesystem I/O primitive evidence of temporary sharing
denial then successful read; source trace of each of the six wait sites and
their no-lock/no-active-provider preconditions. A3 includes a real external
sharing hold on the fixture's existing epoch file during module completion,
then release, proving eventual memory completion rather than intent removal
without memory. A separately reached actual Load/Reset/Quit during that wait
must retain typed cancellation/quiescence. No file-content changes, fake model
responses or production hooks; if the contention window is missed, mark
NOT-REACHED. Do not claim a primitive probe proves live capture continuity.

Evidence block per arm: task ID, reported model (UNKNOWN if not captured),
input-relative latency and capture lines; parsed request fields; complete player
text; diagnostic/degrade counts with grep; fixture provenance; per-file changes
and every nonempty->empty field; PASSED/FAILED/BLOCKED/NOT-REACHED per boundary.
PX review checks five disk-grounded narration claims, second-person PC, grounded
perception, agency, visible acknowledgment/progress and named next action.
Do not interpret a silent skipped T108 or a successful module as memory success.

## 8. Full Part 3 review dispatch

FULL: moving provider/lock ordering, shared admission and failure catches triggers
FS-1/GL-1. Required separate blind seats: Architecture, Fail-Forward (verbatim
B1/B2 in brief), Acceptance, Consumer/Compat, Legacy-Contract, Player-Experience,
Leanness, No-Limits, Single-Path. Nine separate agents, parallel in waves bounded
by available slots; no combined seats or parallel live probes. All read current
frozen plan and full ledger, no author's private reasoning/other review drafts.
Each independently checks gate applicability: Schema-Freeze (no delta, real-file
scan); Platform/Provider (shared lifecycle native proof); Hygiene (ASCII/secrets/
local tests); Limits/FS-1; large-change gate only if actual size crosses threshold.
Sentinels paste raw scans of candidate diff (currently plan only) and all touched
Python files; disposition inherited hits by lineage, never claim code edited.
Unchanged debt is not retroactively ratified; request a falsifiable check before
manufacturing new work. Counterexample required for blocker. Confirmation follows
all-seat convergence per NEQ-REVIEW-11, unless only qualifying polish remains.

## Tracked follow-ups

- #311 owns this repair and its call-path blockers; no separate product changes yet.
- #198 existing async capture lifetime / #293 D-VS-13a: unscoped late writers
  remain unchanged; no claim this plan resolves them.
- #213 chronicle compression and #312 travel narration fidelity remain separate.
- #201/#270 broader lifecycle convergence/control arbitration remain separate.
- #283 recall/affinity redesign remains separate; no selection changes.
- #317 module archive/hopping audit and #318 factual-retention prompt repair
  were owner-requested and separately filed; neither is absorbed here.
- No newly discovered independent defect is silently repaired. New substantiated
  out-of-scope findings get an issue body and filing during review per R9.

## Resolution ledger

| ID | Evidence / disposition | Token |
|---|---|---|
| F1 | Missing snapshots and misleading lock placement, code-proven #311 | task-1 |
| F2 | Save's accepted-control owner cannot currently register required child | task-2 |
| F3a | Scope omitted by consolidation | task-2 |
| F3b | No typed final-memory telemetry | task-3 |
| F4 | Replayed final extraction can overwrite existing canonical content | task-3 |
| F5 | Docs claim final capture works; current code contradicts | task-3 |
| R1-1 | Seven independent seats found canonical-only replay drops unfinished POV; corrected to shared stored-record projection plus independent A2/D1 consumer proofs; code-class, requires all-seat re-review | task-3 |
| R1-2 | GL-1 registration/projection origins corrected; one token per finding; citation/ledger polish only | fixed-inline |
| R1-3 | Sentinels: diagnostic-only slices, identifier/digest formatting, data compatibility and provider wire adaptation are not new narrative caps or duplicated memory runtimes; full raw evidence in local review record | defensible: code-traced non-semantic bounds and shared-path adapters |
| R1-4 | Single-Path found no production caller for inherited manually constructed-manager compatibility; no new issue asserted from comment alone | fyi |
| R3-1 | Nine seats passed round 2 and the clean confirmation on substantive SHA 816b4f3e9080b8dd4260e5bbbb6cbbe0ad414cdd03f81607589258102bb18a89; this status/ledger stamp is polish only, no task/test/code contract change | fixed-inline |
| D-311-1 | Owner approved execution after reviewed plan and lay explanation; implementation/testing only, no merge authorization | override: owner execution approval in current conversation |
| F6 | Real distinct-visit close-17 collision suppresses new final memory; committed visit identity replaces marker count | task-4 |
| D-311-2 | Owner accepted visit identity plus preservation of old memories, with possible one-time duplicate for interrupted older-build saves | override: owner 'accepted' on 2026-09-07 |
| CC-1 / ARCH-1 | Accepted D-311-2 now codified in live #193 Part 5 at 2026-09-07T18:48:35Z; authority/citation correction only | fixed-inline |
| FF-1 | Temporary epoch-read failure at new synchronous checks can become final-memory abandonment; retain ownership and retry observation before capture/projection | task-2 |
| R4-1 | All nine required seats and clean confirmation PASSED substantive SHA 5cc5b4fde08cb4f7c89e7dbe128ca4d8f2f0213557007f1cfdeab9a6c3dc98ae; FF-1 reverified in revised task-2; this row/status stamp is plan-polish only | fixed-inline |
| D-311-3 | Owner approved the presented amended plan for implementation and testing; no merge/push authorization | override: owner 'aoprvoed continue' on 2026-09-07 |

Review verdicts and subsequent revisions will be recorded by the controller.
Round-1 controller consolidation (not verbatim transcripts):
/mnt/c/agent-room-fleet-kit/local-data/311-review-record.md.

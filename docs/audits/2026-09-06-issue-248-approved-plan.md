# Execution approval record

Owner approved the presented final plan on 2026-09-06: "i approve your plan make sure its in a clean work tree and you tt it full before merging".
D-248-1/2 codified in live #193 Part5, epoch2026-09-06T22:48:56Z.
This execution copy preserves the reviewed plan below, including historical gate statuses.
Those historical execution holds are superseded by this approval; ship remains gated on testing/review.
Reviewed-document SHA256: 9a8c7a26fc3607d1e7f0266f5c91eee9906190b5f970823962ab9b20b3629040.
Implementation worktree: /home/loup/neq-worktrees/248-travel-recovery-implementation.
Branch: fix/248-pre-input-travel-recovery. Source review artifacts remain in the planning worktree.

# #248 - Finish interrupted travel before opening a new turn

Status: R5 full review converged with documentation-only polish; ready for owner presentation. PLAN ONLY.
Date: 2026-09-06. Controller: codex-wsl. Worktree: /home/loup/neq-worktrees/248-travel-recovery.
Branch: docs/248-travel-recovery-plan. Observed base: 185f8997a5055521f04fe7a55ca908a41f0d412f.
The revision is review evidence, never a runtime gate. Re-capture ancestry before execution.
Policy: live https://github.com/MoonlightByte/NeverEndingQuest/issues/193 v3.1,
updatedAt 2026-09-06T20:36:18Z at latest read (initial read19:20:13Z).
The intervening D-NPC-PARTY-6 ordering ruling was read: this plan changes neither
candidate normalization nor guardian/route/validator ordering. Recheck at execution.
Owner scope ruling D-248-1: "I aprove the ncludsion" (this session), approving the
narrow recovery controls, queued-Save protection and required cancellation propagation.
This permits their design/review, NOT production implementation. Ruling relayed
to Claude in room9ec3a38b-b2e7-4f78-b27c-ea0aa5ac34ce for #193 codification.

## 1. Outcome and scope

When a saved journey still needs finishing, the harness finishes that SAME journey
before offering another gameplay turn. The player sees truthful recovery progress,
the retained arrival, then a fresh prompt using the resulting location and time.
The player does not have to submit a sacrificial command to wake recovery.

The DM still narrates departure, arrival with location history, and the seamless
combined result through T013/T063/T064. Code orders that work and commits its
existing receipts; it does not invent a replacement arrival or a new player action.
No additional agent call is justified by this scheduling defect.

This is an ordering repair, not a new crash-save system. Existing last clean state
and travel receipts remain authoritative. No durable input inbox, journal, store,
schema, retry budget, timeout, model setting, atlas change or recovery migration.
No implementation, tests requiring provider spend, commit, push or merge in this phase.

README promises: Core Game Systems (AI DM, Save/Load) and Web Interface Features
(real-time state updates), README.md:193-203. Preserve ordinary no-pending startup,
welcome generation, combat, and normal accepted travel.

## 2. Evidence and root cause

OBSERVED, independently reviewed raw artifacts:

- /mnt/c/agent-room-fleet-kit/local-data/303-a5-originalpath-resume-protocol.ndjson:
  prompt seq99 precedes recovered arrival seq200; quiet-action narration seq343
  follows that arrival before next prompt392. Startup welcome reports pending
  transition at126/127. This is not a clean player-experience pass.
- /mnt/c/303-acceptance-20260906/game-a2-amended/debug/api_captures/api_calls_master.jsonl:
  startup welcome32; recovery T013/T063/T064 at33/34/35; quiet-action candidates
  and validation36-39. See 303-A5-SAMEPATH-REVIEW.md beside the protocol for exact
  receipts, retained message ID, timestamps and independent disk comparisons.
- That recovery preserved Keep_of_Doom/C01 at10:50, with the prior120-minute
  receipt already committed. Party/plots/eight area files were byte-identical.
  Thus recovery integrity passed while the input sequencing failed.
- Earlier #248 evidence: C:/pkev/protocol-pk2-restart1.ndjson seq9-14. Historical
  evidence only until re-read; do not use old ledger claims as new runtime proof.

CODE-PROVEN at the observed base:

1. main.py:7577-7643 discovers a pending transition before ordinary startup context.
   It handles blocked/recovered but has no resume_required branch.
2. action_handler.py:1583-1715 distinguishes provider-free inspection from an actual
   v2 continuation; current v2 work returns resume_required with operation_id.
3. main.py:7949-7988 prepares welcome; :8003 signals readiness; :8127-8130 reads
   a new player input. Neither has completed the pending v2 operation.
4. main.py:8617-8642 opens the player's live scope, resumes the old operation, then
   continues processing the SAME input after completion. Context was partly built
   before this resume. This is the root ordering error, not a bad travel model.
5. main.py:1876-2272 owns receipt-based continuation. It includes within-module and
   cross-module handoff, final Save/exit siblings and the retained narration ID.
   Those owners must not be copied into a new recovery implementation.

Lineage (git blame and git show checked, all ancestors of the base):

- 60a7e7766, fix(travel): harden contextual location transitions, introduced the
  deterministic pre-context startup inspection. Its no-double-move goal survives.
- b7f7a8631, fix(travel): make agentic transitions recoverable, introduced the
  v2 post-input resume block. Preserve all v2 semantic work; relocate its ownership.
- 6625cca4d, fix(travel): #210 startup fails forward on un-appliable interrupted
  transition, preserves the owner's discard-and-explain disposition where the
  existing recovery owner has ALREADY discarded an un-appliable record.
- This defect predates #303; the atlas change did not introduce it.

## 3. Spec pin and existing mechanisms

| Datum | Authority | Commit/terminal |
|---|---|---|
| Party location/time | party_tracker.json and existing action receipts | Owning action commit, never new prompt prose |
| Pending journey | existing v2 checkpoint operation_id/phase | Existing complete_location_transition_checkpoint |
| Arrival | Existing narration message_id/text/status | Existing retain/publish path, not a regenerated welcome |
| Running work | Existing LiveTurnScope operation/generation | Exact child reap, owned scope finish/quiescence |
| New action | Real input consumed at a genuine gameplay prompt | Existing validation and state owners |
| Lifecycle control | Existing accepted Load/Reset/Quit identity and queue | Existing quiescence and manager result |

Consulted schematics in full: travel-transitions.md, startup-boot.md,
save-load-reset-lifecycle.md, web-headless-surfaces.md, module-lifecycle.md. Their historic pins are not
current authority; actual anchors above were re-read. Update the changed flow in
all five schematics in the implementation slice, not a duplicate design.
Module-lifecycle Flow16 must distinguish durable module commit from subsequent
episode cancellation: cancellation does not mark work complete or remove the
pending marker. Ordinary advisory-failure policy and receipt ownership stay intact.
This plan supersedes no approved architecture; it replaces the #248-defective
startup/turn ordering described by those documents.

Policy system pins: Part2 p8 NEQ-WORLD-03/04 (history/context and preservation),
p9 NEQ-SAVE-01/02, p10 NEQ-WEB-01/03, p11 NEQ-PROVIDER-01/02/03,
p12 NEQ-SCHEMA-01/02, p13 NEQ-ACCEPT-01/02/03 and NEQ-TEST-01/02.
Part1 B1/B2, AP2/AP4/AP5/AP7; Part3 FS1/GL1; Part4 policy epoch and actual WSL/native
division. The #303 party-guardian controlled-error exception does NOT authorize
fabricated provider results for #248.

Existing controls are usable before an input prompt IF a live scope exists:
headless session.py:622-695 queues Save; :875-895 Load waits quiescence then joins;
:580-607 Reset quiesces before wipe. Web web_interface.py:2971-3004,3074-3104
supersedes/waits outside the game thread. Provider polling checks scope and reaps
before typed cancellation (live_provider_call.py:1122-1157).
Locks must NOT span any provider call or a quiescence wait.

## 4. Proposed implementation, subject to review and owner execution approval

### task-1: One existing continuation, before input

Add a private main.py orchestration helper for the already-existing inspector and
_resume_v2_location_transition; no new recovery pass or state owner. Use it at the
startup inspection seam BEFORE context normalization, welcome and combat resume,
and at the loop boundary BEFORE readiness/input to cover an interrupted surviving
session. Replace the existing post-input continuation block, not duplicate it.
Normal freshly accepted travel still calls the same continuation directly.

The startup OWNERSHIP bracket must begin earlier than the continuation call:
immediately before the staged-module drain at main.py:7488. That predecessor
currently raises through require_staged_module_completions_drained:4273-4277 and
returns at7496-7503, preventing the later recovery controls from being reached.
Select provisional ownership by reading the EXISTING pending transition file,
not by calling the mutating inspector early. Use its existing filename constant
and JSON reader; distinguish truly absent from present-null/unrecognized records
and read failures. A read failure is not evidence of clean absence. Do not add a
second schema validator, derive identity from prose, or guess a repaired record.
Known-present unknown state takes section5's existing unknown-state disposition.
Recheck actual scope authority and reread the record after acquiring ownership.

For pending travel only, run existing retry_staged_module_completions at its
current startup position under that recovery scope: failed -> control wait;
otherwise blocked -> interruptible retry; drained -> continue. Preserve ordered
sibling completion: do not filter out a failed sibling to reach the target faster.
No-pending startup retains its existing require_staged_module_completions_drained
entry and disposition; do not change that shared helper globally.

Keep the SAME scope across the unchanged tracker/path initialization, effects
migration, and location-graph initialization order (main7506-7571). At7577 the
inspector/continuation helper BORROWS it. The startup ownership bracket, not its
borrower, settles and closes it after recovery before combat/welcome/ready. The
surviving-session helper still opens its own scope only when none exists. Do not
move travel narration ahead of effects/graph initialization or copy those systems.

Audit every exit within this extended ownership bracket. If another prerequisite
fails while selected travel remains unresolved, preserve that subsystem's state,
diagnostic and failure classification, but settle through section5's truthful
control-only terminal instead of returning through ordinary scope drain/abort.
This changes only the terminal for the pending-travel case: it does not repair or
retry effects/graph faults as travel work. Normal no-pending subsystem behavior is
unchanged. Accepted Saves must not become snapshots of a partial state, disappear,
or be cancelled merely because a prerequisite failed.

The helper is scope-only: borrow an existing live scope or open one if absent,
record ownership locally, and finish/abort ONLY what it opened. Do not call
combat_execution_authority just to obtain a scope: that also creates a combat
invocation, an unrelated semantic owner. Use existing scope/queue functions.
All exits use a finally; genuine cancellation rethrows after child reap. An
unexpected recoverable fault enters section5's control wait, NOT abort (which
currently fails accepted Saves). Never close a caller-owned scope. Do not
leave the recovery scope registered across welcome spawn or the next ordinary
turn's unconditional open. No new global registry or thread.

Check existing scope supersession before continuation and before readiness;
LiveProviderSuperseded and InvocationSupersededError bypass broad startup failure
handlers. An old result may not publish after an accepted lifecycle supersession.
Use existing provider supervision, with no new timeout or attempt bound. Transient
continuation pending uses the existing interruptible wait/recheck idiom; permanent
conflict is not retried automatically. Section5 specifies all outcomes.

Preserve failure CLASS at the existing module-completion adapter main.py:1792-1795:
completion.failed enters the non-transient control-required disposition; only
completion.blocked retains its existing pending/recheck disposition. If both are
present, failed wins. The current combined predicate loses this distinction.
CampaignManager.drain_module_completion_intents already separates non-transient
failed entries from transient I/O (campaign_manager.py:2859-2879,2898-2909).
Consume those structured fields, not their error prose. No manager rewrite, new
persisted outcome or provider policy change. A failed sibling intent must not keep
the player in an endless automatic retry of the same unchanging failure.

Cancellation propagation is a small explicit exception branch BEFORE broad catches
in main's resumed episode/chronicle calls, core/npc/episode_extraction.py:172,
core/npc/episode_capture.py:217, core/ai/chunked_compression.py:271 and
core/ai/chunked_compression_integration.py:109. Propagate LiveProviderSuperseded
and InvocationSupersededError unchanged. Preserve ordinary unavailable advisory
results and non-cancellation failure handling. Check the active scope after each
called stage and before checkpoint status/publication; cancellation must not become
attempted_unavailable/not_due. Do not redesign T108, compression or their stores.
Shared caller-family audit and no-cancellation negative controls are mandatory.

The same typed-only propagation MUST cover the module-final T108 branch reached
by the startup drain: consolidate_module_episodes at episode_capture.py:531 and
its CampaignManager caller at campaign_manager.py:3620 must rethrow before their
broad catches. Otherwise a cancellation can fall through to work-marker commit
and pending-marker removal (:3625/:3637); existing identity/epoch checks at1163
cannot substitute because an accepted Load is waiting for scope quiescence before
advancing its epoch. Do not roll back already-committed module data, rewrite marker
cleanup, or change ordinary advisory-unavailable policy: prevent cancellation from
falling through those catches, retaining the existing continuation receipts.

Likewise T027's actual provider consumer LocationSummarizer at
core/generators/location_summarizer.py:692 must rethrow the two cancellation types
before its broad catch retries and converts them to RuntimeError(:700). Change
neither ordinary correction handling nor retry policy. This closes the declared
unchanged-type contract; it is not a claim that the existing outer scope check
would otherwise allow stale travel narration.

### task-2: Fresh context and one recovery beat

On completed recovery, reload history, tracker, location, path manager and location
graph/module projection BEFORE subsequent context and prompt preparation. Respect
terminal_action=exit; do not display another prompt or generate a welcome after an
already-accepted exit sibling. Preserve staged Save ordering and action cursor.

When this boot completed and published the interrupted journey, omit the ordinary
return-note injection and welcome call for that boot: the recovered arrival IS its
welcome beat. There is no generic kickoff-skip API: use the existing
claim_kickoff_lease/mark_kickoff_done identity checks to record that this boot's
welcome work is already provided by recovery, only after final context preparation.
Do not call T067 for this receipt, or emit a ready marker until the owned scope is
closed and supersession rechecked. A non-owning claim result is not permission to
mark another attempt done. No-pending and discarded/replan cases retain their welcome.
The process-local completed-recovery result is an ordering fact, not a mode flag.

### task-3: Truthful controls/input boundary

During valid recovery, publish working status through the existing status manager
and provider heartbeat; no gameplay-ready marker, input(), or new T067 welcome.
Save remains accepted/deferred; Load/Reset/Quit supersede the registered scope.
Once recovery, queued safe-boundary controls and fresh projection are complete,
publish ready and one fresh gameplay prompt. No fabricated wake input.

Adapters already queue text independently of input(). Do not silently erase text
that a reconnecting/early client has actually submitted. If received during the
busy phase, its existing queue retains it and the surface explicitly acknowledges
it as waiting for the next actual turn; no consumption during recovery. No promise
to retain uncommitted text across a process crash. If that acknowledgment needs an
adapter change, limit it to the pending-recovery status path and preserve ordinary
queue behavior. No keyword parsing of player intent and no broad busy refusal.

### task-4: Verification and documentation

Apply slices one at a time after approval: C0 evidence/frozen-file inventory;
C1 pre-input orchestration and typed exits; C2 welcome/readiness/context alignment;
C3 local checks + simplifier + independent diff audit; C4 serial real acceptance;
C5 scoped docs/evidence and owner ship presentation. No merge authorization inferred.

Production allowlist: main.py; utils/capture/live_provider_call.py (scope terminal
and queued-Save cancellation only, NOT provider loop); core/headless/session.py;
web/web_interface.py (input acknowledgment and Save outcomes); core/npc/episode_capture.py;
core/npc/episode_extraction.py; core/ai/chunked_compression.py;
core/ai/chunked_compression_integration.py (last four: typed cancellation only);
core/managers/campaign_manager.py (the module-final consolidation catch only);
core/generators/location_summarizer.py (T027 cancellation catch only).
These two added files are explicit task-1 caller-chain repairs under the approved
required-cancellation inclusion, NOT a manager/provider redesign. Ten Python files.
No changes to travel checkpoint schema, provider execution, action receipt writers,
atlas, prompts, model bindings or tests tracked in Git. No frontend edit assumed:
verify existing connected lifecycle controls remain enabled while busy; a proven
consumer gap requires a specific plan amendment, not mid-acceptance repair.
Preserve each file's actual per-region EOL; check diff whitespace and ASCII additions.

## 5. Explicit failure-state decision: review must not hide #211

The existing resume function can return blocked with a retained conflicting receipt,
or raise an error. The current startup broad handler returns/engine_stop (#211).
Moving continuation earlier and retaining that handler could turn a working Load
opportunity into a startup stop. Simply looping forever on the same conflict, or
silently discarding its accepted work, is NOT a fix. Nor may it show a normal
action prompt while the old mutation remains unresolved.

D-248-1 scope inclusion is APPROVED. The concrete proposed contract below remains
subject to full review and final owner execution approval D-248-2, with its queued
Save cancellation behavior explicitly highlighted, not silently assumed unchanged.

### Control wait, not a new controller

Keep the SAME live scope registered on queue-backed web/headless. Its existing
phase becomes RECOVERY_REQUIRED; it retains its pending_saves deque and accepts
lifecycle controls. Keep the game thread inside a private lock-free control wait
which checks supersession using the existing interruptible wait primitive. Do NOT
call input(), service_live_input_boundary (it drains Saves), finish, abort, return
from the engine, open another scope, or continually retry the conflicting write.
The status manager remains processing, with the reason and usable Load/Reset/Quit
actions. Existing input queues may retain early text; no text is sent to the DM.
There is no new store, worker, recovery result masquerading as RestoreOutcome, or
separate controller queue. Existing lifecycle command threads remain the only
Load/Reset/Quit entrants. A phase value is process-local status, not persisted trust.

| Result/failure class | Required disposition |
|---|---|
| none/completed/replan_required or already-discarded #210 | Existing semantics; fresh projection before prompt |
| valid resume completes | Finish safe queued Saves FIFO, close owned scope, fresh context, arrival then prompt |
| transient pending from module handoff, typed transient I/O | Same logical recovery retries through existing interruptible wait; controls/heartbeat remain active, no attempt count or abandonment |
| retained conflict, unrecognized v2 identity/kind, non-transient unresolved exception | Preserve checkpoint/queue; enter control-only wait, disclose named next action; never retire the record or imply completion |
| accepted Load/Reset/Quit supersession | Reap; dispose of unexecuted Saves as below; close/quiesce before existing manager applies the actual control |
| process crash | Existing receipts and last clean saves only; no promise to persist process-local pending text/control callbacks |

The provider's existing transport/advisory policy is not reclassified here. Use
typed status and is_transient_filesystem_error for I/O, never exception prose.
Do not repeatedly retry a deterministic conflicting value. An inspector result
none after a previously known operation requires authoritative reread: only actual
completion/retirement or accepted replacement permits readiness, not an I/O failure
silently converted to None. Preserve unknown state and offer controls otherwise.

### Queued-Save terminal (explicit proposed behavior change)

Publish this player contract during recovery: "Saves wait until this journey
finishes safely. Choosing Load, Reset, or Quit cancels those waiting saves."
Fault or elapsed time alone NEVER cancels a Save. On recovery success, existing FIFO
execution is unchanged. On a validated Load, confirmed Reset, or explicit Quit,
the game-thread owner seals admission under scope.lock, extracts ONLY unexecuted
records from its existing deque, and gives each one a correlated CANCELLED terminal
with its Save ID and the actual superseding control ID. Never invoke its execute
callback. Ordinary started Saves and non-recovery scopes keep their existing FIFO
behavior. Reset's separate durable backup-before-wipe is unchanged.

Add a narrow existing-scope terminal helper, cancel_recovery_saves, with callers
only at this owned recovery terminal. It verifies purpose/phase and actual accepted
supersession under the existing scope lock; no default timed/fault cancellation.
Use an optional cancel callback on queue_live_save's existing record so old callers
keep their (ok,message) result contract. Headless/web callers provide that callback
for recovery-scoped Saves and render cancellation distinctly from failed/saved.
Keep protocol event types/old fields compatible; optional cancellation disposition
and responsible operation ID are additive metadata. No fabricated successful Save.
Caller-family inventory: session.py:690,751,760 and web_interface.py:2881,2907,2917.
The welcome-to-live reroutes at760/2917 need the same exact-scope/cancellation
handling if they admit a recovery-scoped Save; direct entrants are not the whole
family. Non-recovery callers retain the existing completion contract.

Seal-race requirement: session.py:690-695 and web_interface.py:2881-2886 currently
execute Save after queue admission fails. Pass the captured scope explicitly to
queue_live_save. After sealing, inspect that exact scope's terminal: cancelled
recovery completes this Save as cancelled too, never snapshots a later loaded game;
a genuinely safe completion retains the normal save behavior. Never silently bind
the request to a different scope. Hold no scope lock during callbacks or manager I/O.
Cancellation completion precedes quiescence so the outer main handler and headless
finally cannot turn these Saves into failures or execute them a second time.

### Raw terminal control access

Raw terminal keeps its existing synchronous provider mode, with KeyboardInterrupt
as its immediate user cancellation. When recovery needs a choice, display a
control-only menu, not the ordinary PC/stat/action prompt. Extract the existing
menu in _run_terminal_restore into one private menu helper; both real failed Load
and unresolved travel use it. It selects a numbered real save, confirmed Reset,
or Quit only (explicit control syntax, not a parser of gameplay prose).
Return a private main-local typed control selection to the outer terminal launcher,
close/quiesce recovery ownership first, then execute the existing Load/Reset owner.
The outer while loop restarts only on a verified clean result; unsuccessful Load
returns to the same existing menu. No pretending a Load already occurred, new disk
status, repeated main-loop recursion, or second implementation of restore/reset.

D-248-2: implementation approval remains pending after review presentation; the
owner presentation must state the queued-Save cancellation rule above explicitly.
No automatic public issue edits or #193/#293 mutations in this planning phase.
Any NEEDS_OWNER finding drafts the exact escalation for the owner/hub to ratify.

## 6. GL-1 behavioral contract

| Changed ordering/branch | Origin and original goal | Disposition and proving arm |
|---|---|---|
| v2 post-input resume | b7f7a8631 / recoverable travel; finish accepted work once | PRESERVED task-1 at pre-input boundary; A1/A2 |
| Same wake text falls into new T067 | b7f7a8631; process actual player intent | PRESERVED task-3 next genuine turn; A1/A3, no silent drop |
| Startup inspector before context | 60a7e7766; canonical movement/history before narration | PRESERVED task-1/2; A1/A2 |
| #210 discarded-record notice | 6625cca4d / #210; remain at actual location and play | PRESERVED unmodified owner disposition; A6 |
| Normal welcome and live controls | 1f25546c7 / #214 off-thread welcome; prompt responsiveness | PRESERVED no-pending byte/control comparison A5; only recovered-arrival boot omits redundant welcome |
| Retained conflict/error outcome | #211 existing engine-stop problem | RETIRED engine-stop for scoped travel by owner D-248-1; controls preserve data, A6 |
| T013/T063/T064, siblings and retained IDs | existing v2 continuation | PRESERVED unchanged callee; A1/A2/A4 |
| Always drain/fail pending Saves on terminal | b7f7a8631,59296f8f0 / #214 queued and explicit-scope Saves; FIFO | PRESERVED safe completion; waiting recovery Saves explicitly cancelled only by accepted user control under proposed section5; A3/A6 |
| Broad advisory/compression catches | 975f8d7a6,411e9c451; 6ccdcbf6f introduced compression catches, f539b7628 changed logging; advisory failures nonfatal | PRESERVED ordinary unavailable behavior; typed cancellation propagates, A3 |
| Raw terminal failed-Load menu | a51cab33a / #243,#286 existing _run_terminal_restore | PRESERVED shared menu and real manager actions; A6 |
| Completion failed and blocked collapsed to pending | existing module-completion adapter main1792-1795; finish handoff before readiness | PRESERVED completion ordering; task-1 retains structured failure class rather than retrying non-transient failed intents; A6 |
| Startup module-completion predecessor before travel inspector | 715732d55 feat(multi-model): integrate provider-aware game runtime; complete prior module before fresh context, cancellation branch a51cab33a | PRESERVED drain/effects/graph order and no-pending behavior; task-1 selects travel ownership before this drain and routes its unresolved terminal to controls; A2/A6 |
| Module-final episode broad catches | b164fc31f episode consolidation; 4797bfb9a independent feature-review repairs; advisory unavailability does not break completion | PRESERVED ordinary unavailable policy; task-1 typed cancellation bypasses both catches before work-marker completion; A3 |
| T027 retry catch | 759a38937 validation/compression repair; 64516fe46 remove placeholder fallback and add retry; generate real chronicle | PRESERVED ordinary retry/correction; task-1 cancellation is rethrown unchanged without entering local retry; A3 |

The implementer must record exact blame commits for any additional changed welcome
or adapter line before C1; no GL1 'origin unknown' at execution. Other working paths
are not simplifier targets. No loss of episode/memory/relationship or plot work.

## 7. FS-1 and failure trace requirements

- No new deadline, count exhaustion, retry ceiling or shorter provider budget.
- Existing provider reissue remains CONTINUES, with reap-before-reissue; inherited
  provider policy is not re-ratified by this plan. Typed supersession is cancellation.
- Pending valid work completes before readiness; Save queues, Load/Reset/Quit remain
  actionable. No lock held across T013/T063/T064 or any scoped child/quiescence wait.
- Exceptions: typed cancellation must unwind, never be swallowed into a false error.
  Retained conflicts/unexpected faults use section5, not a runtime PASS by assertion.
- An empty/no-operation-ID resume_required is not completion; do not manufacture IDs
  or repair schema here. Its control disposition follows D-248-1.
- Typed rethrows across the episode and chronicle chains are explicit task-1 changes,
  not an audit promise. A non-cancelled advisory failure remains its existing policy.

## 8. Acceptance specified before code

User chose a platform-independent issue instead of native-only #219. Controller
performs WSL work. Real Windows evidence, when required by #193, is a separately
assigned native reviewer arm, not a claim this WSL agent has already run it.
OpenAI-only configured production model; no provider/model tuning in this fix.
Read gameplay guidelines before live runs. One real command at a time; no batches,
state edits or fabricated model responses. Local ignored tests/captures only.

| Arm | Real procedure | Mandatory oracle |
|---|---|---|
| A1 | Authentic pending within-module travel, restart without gameplay input | Actual missing T013/T063/T064 calls/captures; retained arrival precedes first actionable prompt, one retained ID, expected receipt/time exactly once; first new quiet action appears only after new input |
| A2 | Authentic pending cross-module handoff, restart at original valid path | Same ordering; fresh target path/atlas/context; source completion and time not reapplied; no redundant welcome, no prior-module projection |
| A3 | Separate live runs: Save, Load, Reset, Quit during pending recovery | Immediate honest acknowledgment; Save drains at safe boundary; destructive controls reap then actually apply; no stale arrival, no stale new action; fresh prompt only for current selected state |
| A4 | Real surviving-session interrupted continuation; early queued text and final Save/exit siblings when naturally reachable | Recovery owns the old beat, queued intent acknowledged not dropped/reused as wake; final exit honored; no double sibling commit |
| A5 | Clean no-pending startup and ordinary travel, plus existing saved combat | Existing welcome/control behavior and three-call travel unchanged; no added model calls/scope nesting or suppressed normal prompt |
| A6 | Existing legitimately retired residue and authentic retained-conflict cases if available | Separate #210 integrity and player-continuation verdicts; D-248-1 controls remain usable; do not call NOT-REACHED a pass |

A3 additionally covers cancellation during T108 and T027 when naturally reached,
not just T013/T063/T064; no cancelled stage becomes unavailable/not_due in receipts.
A3 distinguishes transition T108 from module-final consolidation T108. For the
latter, cancellation must unwind before work-marker commit/cleanup, without undoing
the module data already committed. T027 cancellation must not become RuntimeError
or consume the ordinary correction loop. Non-cancelled advisory unavailability and
ordinary chronicle correction retain their baseline outcomes. Report each actual
consumer separately; one T108 hit is not proof of both call chains.
A6 covers accepted Save -> unresolved outcome -> validated Load/confirmed Reset/Quit:
Save remains pending until actual user cancellation, gets exactly one cancelled
terminal, no execute callback, no snapshot of replacement state. Negative controls:
invalid Load and unconfirmed Reset must not cancel; normal completed recovery drains
Saves; already-started safe Save remains FIFO; seal-race must not fall through to
direct Save. Reachability/captured-stage limits are explicit NOT-REACHED rows.
A6 additionally separates completion.failed from completion.blocked: an authentic
non-transient failure (including a sibling completion intent) enters control-only
wait without repeated work, while pending completion retains its existing retry.
Do not fabricate a provider or checkpoint to force this polarity; record separate
NOT-REACHED when absent. Include a separately assigned native raw-terminal menu
arm: real numbered Load, confirmed Reset and Quit, without an ordinary action prompt.
A6's failed-completion case must begin at actual boot, not a direct continuation
call: retained cross-module travel plus failed ordered intent must reach recovery
controls through the startup7488 predecessor. Include a no-pending startup negative
control. Record prerequisite-exit coverage separately; never claim a successful
continuation proves the earlier boot failure edge or another subsystem's repair.

Fixture caution: C:/303resbase preserves before bytes but a relocated cross-module
game does not preserve its absolute-path receipt namespace. Do not launch that copy
and misattribute its known relocation failure to #248. Create an isolated official
module fixture through real play; interrupt/restart at the SAME dedicated path.
Use an authentic saved pending record only with verified provenance/namespace.
No manufactured pending record or mocked provider means a hard-to-reach arm remains
NOT-REACHED, with owner disposition required, not a coincidental passing turn.

For every arm: input timestamp; per-call actual returned model/duration/capture
line; parsed relevant request context; verbatim player text with five disk-grounded
claims; prompt/status ordering; operation/message IDs; receipt/cursor/party deltas;
counts of omission/reissue/stale/error events and exact grep; quiescence/orphans.
Hashes prove file comparisons only, never runtime identity. Record natural pending
stage coverage honestly. Historical master logs expose top-level model (not proof
of response.model) without
per-call durations; additional provider timing artifacts are required, not invented.
Native browser check proves disabled input has a reason
while Load/Reset/Exit work. Do not infer that from backend status alone.
Independent transcript reviewer, not the implementing agent, judges player truth.
Dev gates: py_compile, pyflakes undefined-name, focused existing compatibility tests,
raw sentinel diff/file scans, no schema/test changes, per-region EOL/ASCII check.

## 9. Review topology and gates

FULL: entrypoint, ordering replacement, scope/control lifetime, visible readiness.
Nine separate blind seats: Architecture Custodian; Fail-Forward; Acceptance;
No-Limits; Single-Path; Consumer/Compat; Legacy-Contract; Player-Experience; Leanness.
Each gets this same plan/full ledger and checks conditional gate applicability.
Platform-Provider and Hygiene apply; Schema-Freeze verifies zero schema changes and
real compatible pending saves; no new provider branch. Sentinels attach raw scans
of the empty production diff AND proposed touched files, with pre-existing hits
distinguished from proposed behavior. Planning is not a post-code sentinel pass.
Actual reviewer capacity admitted one fresh reviewer at a time in R5; independent
seats ran sequentially, not in parallel. No seats were combined or author-substituted.
Controller is sole writer; no agent edits or live acceptance in parallel.
Any NEEDS_OWNER stops convergence for a ruling; agreement never authorizes execution.
After all required seats are clean on the same SHA, run clean confirmation unless
the exact plan-polish-only exception applies. Then present, not implement.

## Tracked follow-ups

- #211: travel's failure-control facet included under D-248-1; other startup
  faults and record-retirement I/O semantics remain outside this narrow wave.
- #201/#270: broader persistence and competing destructive-control arbitration;
  do not absorb them, and do not claim those races fixed by #248.
- #237: partial-pair recovery ordering; unchanged receipt owner, not this repair.
- #219: native Reset registration/path behavior; user explicitly declined assigning it here.
- #293: owner decisions only through the required NEEDS_OWNER escalation process.

## Resolution ledger

| ID | Evidence/class | Resolution | Status |
|---|---|---|---|
| F248-1 premature ready and wake reuse | #248 +303 A5 OBSERVED, main7579/8619 CODE-PROVEN | task-1 | Draft |
| F248-2 stale welcome/context competition | 303 A5 welcome32 and pending126/127 | task-2 | Draft |
| F248-3 early queue input/controls | session399, web2769 CODE-PROVEN | task-3 | Draft |
| F248-4 earlier resume fault could stop boot | #211, main7636 and resume blocked terminals CODE-PROVEN | task-1 | D-248-1 owner inclusion approved, section5 revised |
| F248-5 no public issue/implementation authority | owner requests plan review only | fyi | Held |
| R1-FF-2 abort loses queued Saves | live_provider_call604-610 CODE-PROVEN | task-3 | Section5 pending/cancelled distinction, R2 required |
| R1-FF-3 nested cancellation swallowed | episode_extraction172,episode_capture217 CODE-PROVEN | task-1 | Explicit chain rethrows, R2 required |
| R1-ARCH-2 spec pins/doc set | review checkpoint | fixed-inline | Correct IDs; five schematics after R5 reconciliation |
| R1-ACCEPT-1 historical timing absence | master32-39 OBSERVED | fyi | Require actual separate timing evidence |
| R2-FF-1 failed handoff classified pending | main1792-1795 and campaign_manager2859-2909 CODE-PROVEN | task-1 | Structured failed versus blocked disposition added; code-class re-review required |
| R2-GL1-1 compression catch lineage | git blame -w271/109 CODE-PROVEN | fixed-inline | Correct origin6ccdcbf6f, not license-header commit699d15e63 |
| R2-COMPAT-1 welcome-to-live Save reroutes | session760/web2917 CODE-PROVEN | task-3 | All six adapter entrants explicit; confirmation required |
| R2-ACCEPT-2 raw-terminal coverage | section5 menu contract | task-4 | Explicit native A6 arm, honest NOT-REACHED |
| R2-POLICY-1 scope ruling codification | owner D-248-1 and room9ec3a38b | fyi | OWNER_RULED_CODIFY relayed to hub; reconcile live Part5 before implementation |
| R2-NL-1 inherited TTS cap | web4565 CODE-PROVEN; #262 tracked | fyi | PRE_EXISTING_OUT, no changed TTS hunk or new cap authorized |
| R2-REVIEW-1 unfinished independent seats | fresh spawn returned agent thread limit reached, including independent relay attempt | fyi | PX and Leanness not run; panel NOT converged; no substitution by controller |
| R3-FF-1 startup predecessor exits before recovery owner | main7488 ->4273-4277 ->7496-7503, campaign_manager2859-2909 CODE-PROVEN | task-1 | Startup ownership begins before travel-associated drain; same scope through unchanged prerequisites; revised-SHA full review required |
| R3-PX-1 hidden-tab notification | socket.ts36-42 CODE-PROVEN | fyi | Observe processing-to-idle title notification alongside A1/A3 browser evidence |
| R4-COMPAT-1 module-final cancellation swallowed | episode_capture531, campaign_manager3620 ->3625/3637 CODE-PROVEN | task-1 | Two typed rethrows explicit; manager added only for this catch; full revised review required |
| R4-COMPAT-2 T027 cancellation transformed | location_summarizer692-700 CODE-PROVEN | task-1 | Typed rethrow at actual provider consumer; ordinary retry unchanged; summarizer added only for this catch |

## Progress / failed approaches
Review polish ledger addition: R5-ARCH-1 | module-lifecycle Flow16 documentation |
fixed-inline | Existing task-4 documentation set reconciled; no runtime change.

Current disposition supersedes historical pending-review statuses below and in
the ledger: all nine R5 seats reviewed SHA6d1cc345a6e79f3edd51d8a817101e8b9a94de5189a364b12b53164e2b217f2e.
All code-class review findings were re-verified; no in-scope code blocker remains.
R5-ARCH-1 is fixed-inline: documentation/citation reconciliation for existing
task-4 only (fifth schematic), no change to code steps, tasks, types, state, tests
or call sites. R5 therefore meets NEQ-REVIEW-11 plan-polish termination after a
full-coverage round; no additional ceremonial confirmation dispatch is required.
The final document differs from the reviewed SHA only by this documentation
polish and review-status bookkeeping. See review-round5.md for seat evidence.
R2-POLICY-1 codification and D-248-2 final execution approval remain outstanding;
convergence is NOT implementation or acceptance sign-off (NEQ-REVIEW-13).

- 2026-09-06: Created isolated planning worktree from main; no code changes.
- Rejected as design shortcuts: same input as unacknowledged wake; a second recovery
  store; dropping T063/T064; substituting a generic arrival; reusing a combat claim
  merely for scope ownership; treating startup errors as clean-ready.
- Review reports and convergence disposition will be added by the controller.
- Owner approved D-248-1 inclusion. Revised concrete scope/control wait and queued
  Save cancellation design is submitted to the full panel; no code exists yet.
- R2: seven independent seats completed on c07c287d; the Fail-Forward code-class
  correction above is folded, NOT yet confirmed. PX/Leanness require fresh reviewer
  capacity. Consolidated evidence is in 2026-09-06-issue-248-review-round2.md.
- Automatic context compaction interrupted the review phase; resumed from the
  durable plan and reviewer returns. This is recorded, not represented as an
  uninterrupted NEQ-OPS-01 phase or a completed full-coverage review.
- R3: PX and Leanness cleared72f0b241. Fail-Forward found the earlier startup drain
  could bypass the entire proposed recovery terminal. Controller verified source
  and715732d55 lineage, obtained read-only placement advice, and folded task-1
  above. No implementation was attempted. Reviews are historical, not approval
  of this revised text. See2026-09-06-issue-248-review-round3.md.
- R4: FF and Architecture cleared adc29533; Consumer/Compat proved two further
  typed-cancellation caller links. Controller verified code/blame and included
  these catch-only repairs above, expanding the explicit allowlist from8 to10.
 No code was written. Review-round4.md records the evidence; full revised-SHA
  review remains outstanding. User execution-if-ready condition is not yet met.


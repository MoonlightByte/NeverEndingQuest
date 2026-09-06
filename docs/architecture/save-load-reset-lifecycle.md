# Save, Load, and Reset Lifecycle

Purpose: Serialize player turns and lifecycle controls so snapshots are consistent,
destructive operations quiesce live work, and session restart follows durable state.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.
- Branch delta: voices `8f51bef3` adds exact headless Reset identity/status, advisory
  child-scope reaping, and companion-memory manifest/restore handling.

## Safety worktree delta (2026-09-05; live acceptance partial)

Save drains/settles completion outside its snapshot locks, then takes party,
combat, module-refresh and campaign locks and rechecks both intents and work.
New work at that boundary releases the locks and retries. Managed-save operations
resolve native owned paths, including receipt replay and junction containment.

Restore returns `selected_applied`, `previous_restored`, `unchanged`, or
`recovery_required`; only a verified clean disposition permits gameplay restart.
Original bytes/membership are frozen in memory and backed up before replacement.
Rollback verifies that inventory rather than re-globbing mutated state. Load
retires old generation authority but preserves ready intents and committed receipts in its rollback
preimage; the new lifecycle epoch is never restored from an old save. Reset
retains backup-before-wipe. Both Reset entrants reconcile canonical pending work
under the existing party/module-refresh/campaign boundary; temporary read faults
release those locks and retry. The subsequent backup/epoch/wipe body is not
replayed by that retry. Neither operation treats active work alone as refusal.

Recovery-required retains control access, not a normal gameplay prompt. The
headless stdin reader receives and queues commands while the existing runner
dispatches them serially. A received Quit can cancel outer read-only Load
preflight at its guarded final check; it cannot retroactively cancel completed
preflight. Received is not accepted or applied. Previously queued Saves still
precede actual Quit supersession. Seven native preflight-control variants and
ordinary Reset are recorded in the execution ledger; these do not prove every
possible race or authentic pending-record contention. Later-Quit versus
already-applying-Load priority remains owner-open #270. Full live controls/I/O
acceptance is not claimed.

Selected absence matters: if a save has no primary combat transcript, Load
removes only that optional live transcript after verifying its backup, then
verifies selected absence. Saved-present transcripts use the normal copy and
verification path. Native OpenAI acceptance proves both fresh combat activation
after absent-history Load and saved-present combat resume without HP/XP changes.

Native fault acceptance also proves that a preparation-cleanup failure after
epoch advancement retains recovery controls: list remains usable, a subsequent
clean Load applies in the same controller, and a real next turn completes after
restart. This does not prove pending-commit partial roll-forward recovery.
Detailed receipts and remaining gates are indexed in local
`validation_evidence/safety_acceptance_remaining.md`; the absent-history and
Load-preparation verdicts there preserve exact protocol and disk evidence.

## Authority table

| Datum | Single source of truth | Commit or acceptance point |
|---|---|---|
| Ordinary outer turn | Sole process-local `_active_scope` | Open before live work; finish/abort after handback |
| Detached welcome | `_welcome_scope` plus `_WelcomeLifecycle` | Game-thread handback owns apply/discard |
| Provider result | `(LiveTurnScope.operation_id, generation)` | Child envelope must echo both before reconstruction |
| Lifecycle control | `supersession={kind, operation_id}` | First accepted authority fences combat and waits for quiescence |
| Queued Save | Queue record operation ID plus completion | FIFO drain at healthy turn finish; no supersession |
| Welcome receipt | `startup_state.json` attempt ID plus lease owner | CAS-like comparison before durable completion |
| Snapshot boundary | SaveGameManager lock order and selected save folder | Metadata and copied state define the save |
| Restore/reset restart | Successful manager result and session restart event | Current game thread is joined or quiescent first |

## Flow

### Welcome versus live scope

1. Queue-backed web/headless startup registers a detached welcome scope and non-daemon worker;
   raw terminal startup runs synchronously.
2. The welcome worker freezes history and generates only; it does not mutate game state/history.
3. The game-thread input pump renews the lease and applies or discards the returned welcome.
4. Player input marks `player_acted`; handback reaps the child and discards stale welcome output
   before processing that input.
5. Save queues during welcome. Load/Reset claim or promote lifecycle authority and execute in
   game-thread handback before the welcome registry becomes quiescent.
6. An ordinary turn opens the sole live scope after real input preparation and marks it
   `MUTATING` immediately before durable response processing.

### Supersession and quiescence

1. Ordinary kinds are `restore`, `reset`, `quit`, and `web_exit`; welcome also accepts
   `player_acted` and `engine_stop`.
2. `LiveTurnScope.request_supersession` is strict first-writer-wins.
3. `claim_destructive_operation` alone promotes `player_acted` to `restore` or `reset`, while
   inserting the executable control under the same scope lock.
4. Provider polling sees supersession, terminates and reaps the exact child, then raises the
   typed superseded terminal.
5. `finish_live_turn_scope` seals controls, drains Saves FIFO, sets `QUIESCENT`, signals waiters,
   and removes the active registry. Abort fails pending Saves before close.
6. A superseded main turn reloads history from disk and reports the lifecycle change visibly.

### Surface entrants

1. Headless NDJSON handles Save, restore, and confirmed Reset; successful destructive operations
   emit restart. At this main pin, headless Reset records `quit` with a fresh UUID rather than
   the command ID; the branch-delta correction is not part of this pin.
2. Web Socket.IO actions are `saveGame`, `restoreGame`, and `nuclearReset`; live Load/Reset fence
   and wait, while welcome Load/Reset queue for handback.
3. Raw terminal has no direct lifecycle-control dispatcher. Model-emitted `saveGame` and
   `restoreGame` actions call SaveGameManager inside the ordinary turn; Reset remains a
   web/headless direct control.

### Save, restore, reset

1. Save lock order is party transition -> completion drain/context refresh -> combat snapshot ->
   module refresh -> campaign transaction -> snapshot.
2. Restore begins combat supersession, takes party/combat/module/campaign authority, validates
   the save, bumps lifecycle epoch, backs up current essentials, copies saved state, and performs
   compensating rollback on copy failure before clearing old receipts.
3. Reset quiesces where the surface implements it, begins invocation supersession, takes
   party/module/campaign authority, creates a durable backup, bumps epoch, resets modules/global
   state, and clears generated state.

## State and atomicity

- Active/welcome scopes, supersession, pending Save deque, controls, and quiescence Event are
  process-local.
- `startup_state.json` uses sibling temp plus `os.replace` under `startup_state.lock`.
- Save is lock-consistent directory copying, not one atomic directory publication; metadata is
  written before and after copying, and individual skipped files can coexist with success.
- Restore is multi-file with a unique essential backup and compensating rollback.
- Reset is backup-before-wipe and multi-phase; this pin has no rollback after phase two begins.

## Load-bearing seams

1. `utils/capture/live_provider_call.py:96-333` - live/welcome scope authority, promotion, queues, and quiescence.
2. `utils/capture/live_provider_call.py:603-714` - child polling, reaping, and correlation gate.
3. `main.py:298-378` - welcome ownership and generation-only worker.
4. `main.py:392-530` - handback ordering, attempt/lease receipt, and reconciliation.
5. `main.py:753-924` - input pump, teardown, welcome registration, and worker start.
6. `main.py:8231-8258` - ordinary live scope opening.
7. `main.py:8888-8904` - mutation boundary.
8. `main.py:9122-9163` - superseded and normal turn terminals.
9. `core/headless/session.py:379-693` - headless lifecycle commands (reset/quit at :379-466) and restart.
10. `web/web_interface.py:2614-2959` - web input and Save/Load/Reset entrants.
11. `updates/save_game_manager.py:465-519` - Save lock and snapshot sequence.
12. `updates/save_game_manager.py:683-934` - restore validation, backup, copy, rollback, and cleanup.
13. `utils/reset_campaign.py:395-447` - reset backup-before-wipe ordering.

## Invariants

- #193 Part 1, Prime Directive, B1/B2, AP-4, evidence, and lineage.
- #193 Part 2, Combat; Save/restore/reset; Web/threading; Schema; Acceptance.

## Open items

- #154/#201 - snapshot coverage and crash-safe convergence.
- #219/#220/#225/#226 - Reset path/platform integrity defects.
- #221/#227/#231 - reconnect, progress, and console-status presentation.
- #234/#235/#236 - wizard/headless Save and restore behavior.
- #243/#270 - combat control scope and concurrent destructive arbitration.
- #263 - owner-deferred pre-combat checkpoint; never combat autosave.

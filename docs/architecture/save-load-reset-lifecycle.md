# Save, Load, and Reset Lifecycle

Purpose: Serialize player turns and lifecycle controls so snapshots are consistent,
destructive operations quiesce live work, and session restart follows durable state.

- Revision: `main` at `20f2b0eaf142c33b7f509ce072b55c6a799dfe66`
- Verified: 2026-09-01
- Doctrine: [GitHub issue #193 v2.3](https://github.com/MoonlightByte/NeverEndingQuest/issues/193)
- Branch delta: voices `8f51bef3` adds exact headless Reset identity/status, advisory
  child-scope reaping, and companion-memory manifest/restore handling.

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
3. Terminal reserved commands enter the same session/backend lifecycle operations.

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

1. `utils/capture/live_provider_call.py:96-134` - scope identity, phase, generation, supersession.
2. `utils/capture/live_provider_call.py:140-192` - live registry and combat fence.
3. `utils/capture/live_provider_call.py:195-246` - welcome registry and Save queue record.
4. `utils/capture/live_provider_call.py:249-333` - promotion, queue, finish/abort quiescence.
5. `utils/capture/live_provider_call.py:603-714` - child polling, reaping, correlation gate.
6. `main.py:298-378` - welcome ownership and worker terminal.
7. `main.py:392-417` - handback drain-before-clear-before-quiescence.
8. `main.py:420-530` - attempt/lease receipt and supersession reconcile.
9. `main.py:753-871` - input pump, discard-before-process, teardown.
10. `main.py:876-924` - welcome scope registration and worker start.
11. `main.py:8231-8258` - ordinary live scope opening.
12. `main.py:8888-8904` - mutation boundary.
13. `main.py:9122-9163` - superseded and normal turn terminals.
14. `core/headless/session.py:495-693` - headless lifecycle commands and restart.
15. `updates/save_game_manager.py:465-519` - Save lock/snapshot sequence.

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

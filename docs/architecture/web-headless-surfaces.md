# Web, Headless, and Terminal Surfaces

Purpose: expose one authoritative game loop through terminal, legacy/React web, and headless NDJSON while keeping frontend stores and narration non-authoritative.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

## Safety worktree delta (2026-09-05; live acceptance pending)

Parked input services accepted Saves and checks supersession before Ready/prompt
and before returning input. Model-emitted Load uses typed control unwind, not a
restore inside an active gameplay mutation fence. Web/React/legacy consumers use
the manager's restore disposition: recovery-required keeps Load/Reset/Quit controls
available without automatically restarting mixed state. Headless similarly keeps
recovery command intake after a failed restore. No frontend projection is state
authority. Headless transport now receives commands on its existing stdin thread
and dispatches them FIFO on the existing waiting runner thread. Received is not
accepted/applied. Only outer read-only Load preflight observes a received Quit;
inner application/rollback remains unaffected. Native cancellation acceptance
must be verified separately; do not infer it from these source contracts.

TypeScript checks pass on native Windows and Linux; the production asset build
passes on Linux with existing dependencies. Actual native React and legacy
failed-Load controls retained recovery intake and applied a subsequent clean
save from the same page; selected files matched the save. These scoped browser
checks do not establish universal quiescence or automatic server restart.
Legacy Reset's inherited cp1252 failure and Reset backup fidelity remain explicit
owner ship decisions. Follow the safety execution ledger for exact P/S verdicts.

Startup delta verified 2026-09-05 against the `fix/issue-114-startup-repair` working candidate based on `3f521f70429cf9bef4e0a5688d11c4fce44f7596`. Changed startup seams below use that candidate; unchanged surface anchors retain the earlier pin. Live #193 controls on conflict.

## Authority table

| Datum | Source of truth | Acceptance or commit point |
|---|---|---|
| Gameplay state | Canonical module/campaign JSON and owning managers | Owning subsystem's durable write |
| Gameplay sequence | One `main_game_loop` invocation on the session engine thread | Engine thread consumes input and invokes the owning subsystem |
| Player input | Builtin stdin, `WebInput`, or `HeadlessInput` boundary | Becomes gameplay input only when engine-thread input consumes it |
| Player narration | `display_dm_narration` plus the currently claimed optional sink | Sink accepts it; otherwise terminal print remains the fallback |
| Web reconnect history | `game_interface_cache.json` | Locked merge and safe JSON write; delivery ledger only |
| Web lifecycle projection | Server game thread, status managers, server-instance ID, and monotonic UI revision | Correlated snapshot/events are emitted |
| React event contract | `web/frontend/src/contract/events.ts` | Sole socket owner dispatches frozen events |
| React stores | Server projection for the current hydration identity and revision | Disposable cache; disk/server can replace it |
| Headless protocol | `core/headless/protocol.py` v1 | Locked writer assigns sequence and flushes one JSON object per line |
| Headless state | Fresh disk projection | Read at prompt or explicit state command |
| Save/Load/Reset | SaveGameManager and reset code under lifecycle authority | Writer finishes; successful destructive control restarts the session |

## Flow

1. Terminal setup calls the shared `main_game_loop`; builtin `input` blocks on stdin. With no claimed frontend sink, structured narration falls back to stdout.
2. `run_web.py` serves built React at `/play/` when available and legacy `/` otherwise. Both connect to the same Flask-Socket.IO backend.
3. Web `start_game` reuses a living `game_thread`; otherwise it installs `WebOutputCapture` and `WebInput`, claims the output sink, resets delivery cache state, and starts exactly one daemon game thread.
4. A separate output-pump thread drains and emits queues only. It never runs gameplay.
5. Socket `user_input` persists/emits the visible player command, then places text on `user_input_queue`; engine-thread `WebInput.readline` consumes it.
6. Structured DM output enters the sink, durable message cache, and game output queue. Captured legacy prints use the same delivery channel before the pump emits Socket.IO events.
7. On connect, web authenticates when configured, announces capabilities/server identity, loads the durable cache before recovery writes, claims the sink, performs provider-free recovery, replays cached output, reports a living game, and drains queued output.
8. React starts a hydration epoch and requests location, party, initiative, UI, player, plot, and storage projections. Request ID, server instance, and per-resource revision reject stale replies.
9. Legacy consumes the same backend events without making its DOM state authoritative.
10. Save queues at a live/welcome safe boundary. Load/Reset supersede a live scope or atomically claim a welcome terminal; a closed scope waits and redispatches. State mutation remains in lifecycle managers, and success restarts.
11. Headless installs stdout, stderr, stdin, lifecycle callbacks, and its structured sink before importing the engine; it emits `hello` and starts one engine thread on `main_game_loop`.
12. A separate headless reporter emits module progress. Input lines are typed `input` or correlated `command` objects, not raw gameplay-side mutation.
13. When the engine reaches `input`, headless emits a prompt followed immediately by a fresh disk state projection. Commands return correlated result events.
14. Successful headless restore/reset quiesces or supersedes live work, commits through the lifecycle manager, and emits an exit/restart terminal so stale memory cannot continue.
15. There is no surface-specific model-call order. Startup, combat, travel, module, and progression schematics own their T-order; this surface owns transport ordering around input, commit, delivery, and projection.
16. A living web game thread is not proof of a playable character. Reconnect emits the startup projection before `game_resumed`; snapshots preserve `in_progress` versus `ready`. An idle wizard prompt permits interview input without enabling play mode.
17. Both browsers keep Save/Load/Reset accessible during connected setup. React separates lifecycle availability from `gameReady`; legacy separately tracks startup input permission. A ready marker triggers fresh authoritative React projections for character and location.

## State and atomicity

- Web/headless input queues hand text to the sole engine thread. Game/debug/module queues are delivery-only.
- Web cache mutation takes an interprocess writer lock, rereads and merges by message ID, then uses safe JSON replacement. Reconnect output cannot become world authority.
- `ProtocolWriter` serializes headless event sequence allocation and output under one lock and flushes every event.
- React accepts one correlated UI snapshot into its in-memory operation/session projection and maintains per-resource revision floors.
- Save/restore/reset take the party-transition authority, but the game is not one global transaction; each subsystem owns its durable receipts and recovery.
- Sink ownership uses an RLock. A missing or failed sink is nonfatal and falls back to console, so importing web modules cannot swallow terminal/headless narration.
- Web cache and browser stores preserve delivery continuity, not canonical mechanics. A fresh disk projection wins on reconnect or state request.
- The prompt-plus-state headless pair is the turn observation boundary: the prompt opens input only after preceding durable work, and the following state is read from disk.

## Load-bearing seams

1. `main.py:4295-4319` - structured narration sink and terminal fallback.
2. `main.py:7007-7007` and `main.py:7743-7758` - shared loop and input boundary.
3. `main.py:9172-9295` - terminal entry.
4. `web/shared_state.py:33-67` - sink ownership and failure semantics.
5. `web/web_interface.py:226-452` - queues, game thread, revisions, and durable cache.
6. `web/web_interface.py:842-899` and `web/web_interface.py:5743-5776` - blocking web input and both routes.
7. `web/web_interface.py:2506` - startup projection, ordered reconnect, and snapshot truth (startup candidate).
8. `web/web_interface.py:2638-2961` - Save/Load/Reset dispatch and restart.
9. `web/web_interface.py:3081-3111` and `web/web_interface.py:4589-4746` - one game thread and output pump.
10. `web/frontend/src/services/socket.ts:145`, `web/frontend/src/stores/session.ts:68`, and `web/frontend/src/components/layout/HeaderBar.tsx:63` - ready refresh, interview/play permissions, and lifecycle availability (startup candidate).
11. `web/frontend/src/services/hydration.ts:51-187` - correlation, coalescing, and stale rejection.
12. `core/headless/protocol.py:5-116` - NDJSON protocol and serialized writer.
13. `core/headless/streams.py:30-151` - output capture and blocking queue input.
14. `core/headless/session.py:56-205` and `core/headless/session.py:300-467` - adapters, engine, prompt/state, and commands.
15. `core/headless/state_reader.py:5-142` - disk-only state projection.

## Invariants

- See #193 Part 1 for B1/B2, AP-1 through AP-7, evidence, and lineage.
- See #193 Part 2 pages 9 through 13 for lifecycle controls, one game thread, provider/startup fall-forward, compatibility, and native acceptance.
- See #193 Part 5 for structural liveness, No-Limits, and Single Path.
- This document describes the pinned implementation. If it conflicts with current #193, #193 controls.

## Open items

- Web delivery and UI: #79, #116, #212, #218, and #221.
- Liveness and controls: #186, #214, #243, #248, and #270.
- Persistence/reset: #154, #201, #219, #220, #225, and #226.
- Headless protocol/product gaps: #227, #229, #234, #235, and #236.

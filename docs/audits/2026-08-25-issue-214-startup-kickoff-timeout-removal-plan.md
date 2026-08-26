# Issue #214 — Remove the 120s startup-kickoff timeout; structural liveness instead

## Spec pin

- Live authority: GitHub issue #193 v1.7 (fetch live before each review round / execution; epoch pinned at session start). Part 1 B1 (fail-forward / Load never refused), B2 (limits taxonomy; deadlines that abort a gameplay-reachable call are BANNED; liveness is STRUCTURAL; abandonment != cancellation), AP-1 (timeout smuggling), AP-2/GL-1 (goal-losing simplification), evidence rules. Part 2 page 9 (Save/restore/reset: Load NEVER refused; resume shows where you were, never a blank screen), page 10 (Web/threading: one game thread; unbounded-on-the-thread resolved by STRUCTURE not a deadline; >~10s waits show live status; tab-hidden completion signalled), page 11 (Provider routing & startup is a play path; create_completion thin router; no max_tokens), page 13 (Acceptance: real native headless/browser, one op at a time, gate-polarity negative controls). Part 5 Decision Ledger: **D-6** (this exact "startup-kickoff 120s abort" is named timeout-debt requiring keep-with-waiver or structural replacement — this plan chooses structural replacement) and **D-1** (OPEN: off-thread worker scope — engaged by decision D-214-1 below; escalated, never decided by fiat).
- Dynamic execution pins: branch `fix/214-remove-startup-kickoff-timeout` off `travel-recovery-clean` @ `fb18a0cc`; `origin/main = 691b5a2f` is an ancestor (verified). Native Windows, configured real OpenAI provider; local LM Studio `google/gemma-4-12b-qat` (thinking off) for the slow-model arm; browser port per travel convention. Revisions are evidence, never authority.
- Player promise advanced (page 9 + README resume UX, #116/#79): a resumed game delivers its welcome-back narration and reaches a playable prompt — even when the model legitimately takes minutes — and never freezes, aborts the welcome, or blanks the screen. Token/cost promise (page 11) is not regressed.
- OBSERVED failure (native Windows + non-thinking Gemma, Codex revalidation `docs/audits/2026-08-25-travel-recovery-windows-gemma-fb18a0cc.md`): real debug stream `INITIALIZATION: Startup kickoff did not complete cleanly: {'status': 'failed', 'reason': 'timeout'}`. The first 120s startup worker expired during startup work; the forced second attempt also expired. The game reached a playable prompt at the correct location (E05) but delivered NO welcome narration. The context plumbing itself worked (the late response placed the party in Storage Vaults/E05).
- CODE-PROVEN root cause (`main.py` on this branch):
  - `_run_get_ai_response_with_timeout` (main.py:292-301) submits `get_ai_response` to a `ThreadPoolExecutor` and awaits `future.result(timeout=120)` (called at main.py:345 with `timeout_seconds=120`). On expiry it calls `future.cancel()` on an already-running future (a no-op) and `executor.shutdown(wait=False)` — the in-flight provider / local-model call is **ABANDONED, not cancelled** (B2-iii break; AP-1 scar T104/#166). Timeout branch: main.py:433-445 marks `kickoff_timeout`; the single forced recovery (main.py:461-512) repeats the same 120s, so one slow startup can leave two abandoned in-flight calls hammering a single-worker FIFO local model.
  - The kickoff uses `get_ai_response` with `live_selected=False`, which SKIPS the existing B2-iii live-provider machinery. `capture_and_fanout` routes `live_selected=False` to `_fire_primary_with_retry` (bounded 3x on empty-response only, no timeout) or a plain synchronous call (`utils/capture/multi_model_capture.py:349-476`). The existing structural watchdog + heartbeat + fresh-subprocess reissue with **no terminal deadline** lives in `utils/capture/live_provider_call.py:389-521` (watchdog 600s is a REISSUE trigger, not a terminal abort; heartbeats every `_HEARTBEAT_SECONDS`) but is wired ONLY to live-selected turns. So the kickoff has neither heartbeat liveness nor structural reissue; its stuck/slow-transport ceiling is the openai-python SDK default (~600s total, `utils/openai_client.py:37-44` sets none) which is itself a terminal abort that would truncate a slow-but-alive local model.
  - Fall-through (main.py:6685-6704): on non-`done`, only a `warning()` logs; control falls into the `while True` main loop where Save/Load/Reset input is reachable. The kickoff runs ON the single web game thread (`web/web_interface.py:4342-4350`, daemon `game_thread`) and blocks it. So TODAY Load is reachable ~120s after startup even on timeout; running to completion extends how long the thread is blocked before input.
- Existing intent being preserved (main.py:6679-6681 comment): "Startup must never hide an unbounded provider call before Save/Load/Reset are reachable." This is a legitimate B1 goal (Load reachability) that the 120s deadline implemented in a B2-illegal way. The fix must preserve the GOAL by structure, not keep the banned deadline.
- Files expected to change: `main.py` (startup kickoff only) and ignored/local tests. Not touched: provider router / `create_completion` / `api_client` response semantics, model registry, prompts (except the narrow resume-note wording in Task 4 IF the owner approves D-214-3), schemas, persistence, combat, the lease-state module's TTLs.

## Owner decisions (execution BLOCKED while open unless the owner defers)

- **D-214-1 (Load-reachability during a multi-minute welcome wait) — RECOMMENDED: (A) block-with-liveness.** The kickoff runs on the game thread; removing the deadline and running to completion means Save/Load/Reset become reachable only after the welcome completes (could be minutes), whereas today they are reachable ~120s after startup. Options:
  - **(A) Block-with-liveness (recommended):** run the welcome to completion on the game thread, routed through the existing live-provider path so the player sees ongoing heartbeat progress ("recalling your journey…") during the wait and the welcome is delivered when ready. Simplest; reuses existing machinery; matches "let the model run." Residual: Load is not reachable until the welcome finishes; a provider that is truly DOWN (not merely slow) would keep the player on the loading screen — mitigated by the live path's fresh-connection reissue surfacing status, but Load is still gated on completion.
  - **(B) Off-thread welcome:** run the welcome kickoff on a background worker so the main loop (Save/Load/Reset) is interactive immediately and the welcome streams in when ready, with genuine cancellation if the player acts first. Best satisfies BOTH "let the model run" and "Load always reachable," but ENGAGES the parked **D-1** (off-thread worker scope) and is materially more complex. Escalate to owner.
  This decision determines Task 2/Task 3 shape and is the plan's central B1/B2 tradeoff. Recommendation A; escalating because it interacts with D-1 and page-9 Load reachability.
- **D-214-2 (pre-kickoff blocking compression call at main.py:6682) — RECOMMENDED: make the startup save non-blocking.** `save_conversation_history(conversation_history)` at main.py:6682 defaults `allow_compression=True`; when the location has >=15 pairs it fires an unbounded main-thread summarization provider call (`incremental_compression.py:251-253`) BEFORE Save/Load are reachable — a second pre-loop blocking call the 6679-6681 comment's own intent argues against. Recommended: pass `allow_compression=False` at this one startup save (compression still happens in the per-turn loop where it belongs), keeping the startup path free of blocking provider work beyond the welcome itself. Alternative: leave to #213 (compression backlog). Flagged because it touches compression scheduling.
- **D-214-3 (resume-note wording vs updatePlot) — RECOMMENDED: no keyword guard; narrow note wording review only.** OBSERVED: the slow Gemma welcome emitted an `updatePlot`. Investigation confirms plot state IS injected into the kickoff context and `updatePlot` is ungated (`action_handler.py:3265-3271`, allowed any turn), so a welcome that updates the plot CAN be legitimate (plot updates can happen at any time) — it is NOT a contract violation by construction, and MUST NOT be patched with a scenario-specific or keyword rule (AP-7). The only question is whether the resume note's wording over-implies "narration only." Recommended disposition: verify on real captured data whether the emitted updatePlot reflected a real plot change; if the note wording is misleading, adjust ONLY the advisory note text (T067 owns intent), never add a deterministic action gate. If the wording is fine, this is a documented non-finding.

## Minimal implementation

### Task 1 — Remove the 120s deadline and the abandonment; route the kickoff through the existing B2-iii live path

**Files:** `main.py` (startup kickoff region only); ignored/local tests.

1. Delete `_run_get_ai_response_with_timeout` (main.py:292-301) and its call at main.py:345. The startup kickoff's model call is made through the SAME live-provider path real player turns use (`get_ai_response` with the live-selected policy that routes to `call_live_provider`, `utils/capture/live_provider_call.py`) so it inherits: heartbeat liveness, fresh-connection reissue on stuck transport, and NO terminal deadline. Confirm T067/main-dm is an eligible live task id (`live_provider_call.py` `_REQUIRED_TASK_IDS`) so the kickoff call qualifies; if the kickoff currently forces `live_selected=False`, flip only that startup call to live selection — do not change routing for any other caller.
2. Delete the `except FuturesTimeoutError` branch (main.py:433-445) and the timeout-driven `kickoff_timeout` semantics. Keep the generic `except Exception` failure marker (main.py:446-458) for genuine non-timeout errors. Keep the exactly-once lease machinery (`claim_kickoff_lease` / `renew_kickoff_lease` / `lock_kickoff_processing` / `mark_kickoff_done`) unchanged — its job (prevent a double first-turn across threads) is real and not a deadline.
3. In `run_startup_kickoff_with_recovery` (main.py:461-512): the "one forced recovery" existed to retry after a timeout. With no timeout, a completed call returns `done`; a genuine error still marks `kickoff_failed`. Preserve exactly-once and the single forced-recovery-on-genuine-error semantics; remove only the timeout-specific retry rationale. No new retry/bound introduced (FS-1).
4. Do NOT pass any `timeout=` to the provider on this path; the live path's 600s watchdog is a REISSUE trigger (B2-iii CONTINUES), not a terminal abort. Confirm no SDK terminal timeout truncates a slow-but-alive local model on the live path.

### Task 2 — Liveness during the (now unbounded) wait

**Files:** `main.py` and/or the existing status wiring; ignored/local tests.

1. With the live path (Task 1), heartbeat `_emit_working` events fire during the wait. Verify the web layer surfaces ongoing progress during startup (STARTUP_MARKER `in_progress` at `web/web_interface.py` + heartbeats) and that the UI does not sit on a static "Starting…" with no motion for minutes (page 10: >~10s waits show live status; tab-hidden completion signalled). Add the minimal wiring only if a gap is proven by a real transcript — no new mechanism absent an observed gap (AP-4/AP-5).
2. Under D-214-1(A), the game thread is blocked until the welcome completes; ensure the pre-kickoff `startup_kickoff_attempted` in_progress state persists visibly and transitions to `game_started` on completion. Under D-214-1(B), implement the off-thread worker per the owner ruling (separate design; engages D-1).

### Task 3 — Preserve Load reachability per D-214-1

1. Under (A): document and accept that Load is reachable after the welcome; prove via acceptance that the welcome DOES complete on the slow (multi-minute) local model and the game then reaches input. No new deadline is added to force earlier reachability (that would re-introduce the banned pattern).
2. Under (B): the off-thread worker keeps input reachable throughout; prove Load works mid-welcome and the background welcome is genuinely cancellable (not abandoned) if the player Loads first.

### Task 4 — updatePlot legitimacy + optional note wording (D-214-3)

1. From the real captured resume run, determine whether the emitted `updatePlot` reflected a genuine plot change given the injected plot context. Report honestly: legitimate (no change) or a note-wording over-restriction (advisory-note tweak only) — never a deterministic gate.

### Task 5 — (if owner selects D-214-2) startup save non-blocking

1. Pass `allow_compression=False` at the startup `save_conversation_history` (main.py:6682) so no compression provider call blocks the pre-loop path; per-turn compression is unchanged.

## Verification and real acceptance

1. Red/green ignored local tests around the kickoff wiring (deterministic: the kickoff no longer imposes a 120s deadline; the live path is selected; the lease exactly-once path is preserved). `py_compile main.py`; `git diff --check`. Diff assertion: the production change is confined to the startup kickoff region of `main.py` (+ the one save flag if D-214-2). No provider-router/response-format/registry/schema/persistence change.
2. GATE-POLARITY (the core proof): reproduce the exact OBSERVED failure — native Windows + non-thinking Gemma, a resume whose startup work takes multiple minutes — and show the welcome now COMPLETES and is delivered, the game reaches a playable prompt, and no `reason: timeout` / abandonment occurs. One operation at a time. Capture the real request/response, actual `response.model`, wall-clock duration (proving a >120s call completed), the displayed welcome transcript, and the on-disk state (E05 authoritative).
3. Native Windows + OpenAI resume: welcome completes and reaches input; the #210 player-stream guarantees (clean notice, authoritative E05 note, no stale E03) remain intact (regression check — this plan must not disturb the shipped #210 fix).
4. LIVENESS: on both providers, capture the player-visible stream during the wait and confirm honest ongoing progress (heartbeat/in_progress), not a silent multi-minute freeze; confirm tab-hidden completion signal (page 10).
5. LOAD REACHABILITY per D-214-1: exercise the chosen option's Load path and show the game stays playable (A: after welcome; B: during welcome, with genuine cancellation).
6. updatePlot: adjudicate the real captured resume actions per Task 4.
7. Browser (React `/play/` and legacy `/`) resume on fresh copies: welcome delivered, next command accepted, complete transcripts/screenshots/server streams preserved. No synthetic/monkeypatched/model-free evidence (page 13).
8. Any residual `reason: timeout`, abandoned in-flight call, silent multi-minute freeze, truncated slow-model call, disturbed #210 behavior, or duplicate first-turn is FAILED.

## Stop conditions

- If removing the 120s fence exposes a DIFFERENT terminal deadline (e.g. an SDK default) that truncates a slow-but-alive local model, that deadline is in-scope for this plan (route through the live watchdog/reissue) — not deferred.
- If the live-path routing changes behavior for any NON-startup caller, stop and re-scope (startup-only change).
- Two failed real attempts on one symptom -> two-strikes/layer-down; do not add a deadline or a keyword guard to force a pass.

## Tracked follow-ups

- #213 (synchronous startup compression backlog) is the TRIGGER that makes startup slow; this plan removes the MECHANISM (the 120s abort) that turns slow into "player gets nothing." D-214-2 optionally removes one pre-kickoff blocking compression call; the broader backlog remains #213 (owner-deprioritized).
- D-1 (off-thread worker scope) is engaged only if the owner selects D-214-1(B); otherwise untouched.
- D-6 startup-kickoff item is resolved by this plan (structural replacement).

## Resolution ledger

- R-1 (B2/AP-1): the 120s deadline + `future.cancel()`-on-running-future is abandonment, not cancellation; removed, not tightened.
- R-2 (B2-iii, no new mechanism): liveness/reissue is provided by routing the kickoff through the EXISTING live-provider watchdog/heartbeat path, not by adding machinery (AP-4 safe).
- R-3 (GL-1): the 120s timeout's origin (`715732d5`) goal — keep Save/Load/Reset reachable if the first call hangs — is PRESERVED by structure (D-214-1 choice + fresh-connection reissue so "stuck" self-heals), while the banned deadline mechanism is RETIRED (issue #214 + B2). See Behavioral Contract below.
- R-4 (Acceptance): gate-polarity proof is a real multi-minute startup that now completes; durable-prompt-without-welcome is explicitly a FAIL, not a pass.
- R-5 (AP-7): updatePlot is ungated and plot is in context; no keyword/scenario guard is added; disposition is verify-and-report (D-214-3).
- R-6 (scope): a second pre-kickoff blocking compression call exists (main.py:6682); surfaced as D-214-2 rather than silently changed.

## Behavioral Contract (GL-1)

| Deleted/changed element | Origin | Goal | Disposition |
|---|---|---|---|
| `_run_get_ai_response_with_timeout` + 120s call (main.py:292-301,345) | `715732d5` (multi-model runtime integration) | Keep Save/Load/Reset reachable if the first provider call hangs; don't hide an unbounded call before the loop | **RETIRED** (deadline mechanism, banned by B2-i; issue #214 owner mandate). Goal PRESERVED via D-214-1 choice + live-path fresh-connection reissue (stuck transport self-heals) + heartbeat liveness. Real A/B: slow-model startup now completes AND (per D-214-1) Load reachable. |
| `except FuturesTimeoutError` kickoff-timeout branch (main.py:433-445) | `715732d5` | Mark a timed-out kickoff failed and allow one forced retry | **RETIRED** (timeout-specific). Generic error marker preserved; exactly-once lease + single forced-recovery-on-genuine-error preserved. |
| kickoff `live_selected=False` (non-live routing) | current | (implicit) treat startup as a non-live call | **CHANGED to live selection** so the kickoff inherits the existing B2-iii watchdog/heartbeat/reissue. A/B: startup call now shows heartbeats and reissues a stuck transport instead of silent-then-abandon. Startup-only; no other caller changed. |
| startup `save_conversation_history(..., allow_compression=True)` (main.py:6682) [D-214-2] | current | opportunistic compression at startup save | **PROPOSED RETIRE of the startup compression side-effect** (allow_compression=False), preserving the save; per-turn compression unchanged. Owner-gated. |

# #214 — CODEX INDEPENDENT REVIEW HANDOFF (pre-implementation)

**Ask:** independent review of the CONVERGED #214 plan BEFORE any code is written. This is the dual-agent discipline (#193 Part 4): Claude authored the plan; Codex reviews independently. No production code exists yet — review the DESIGN/SPEC, not a diff. After your review converges with the owner, Claude implements, and Codex owns the authoritative native-Windows + Gemma acceptance.

## Dynamic pins (verify before reviewing; STOP on mismatch)
- Branch: `fix/214-remove-startup-kickoff-timeout`
- HEAD: `4f740a4c` (this handoff will advance it by one commit)
- Base: `travel-recovery-clean` @ `fb18a0cc`; `origin/main = 691b5a2f` is an ancestor (verified).
- Policy source: GitHub issue #193 (fetch LIVE; epoch at authoring `2026-08-24T05:39:19Z`). Re-check `updatedAt` before reviewing.
- Plan under review: `docs/audits/2026-08-25-issue-214-startup-kickoff-timeout-removal-plan.md`. Read the "EXECUTION-READY CONSOLIDATED SPEC" (12 steps) + "PANEL ROUND 2 (B-architecture) — findings folded" + "OWNER RULINGS" + "Verification and real acceptance". Issue: #214.

## What the plan does (one line)
Remove the banned 120s startup-kickoff timeout (it ABANDONS the in-flight call — `future.cancel()` on a running future is a no-op); let a slow local model run to completion by routing the kickoff through the EXISTING live-provider path; make the resume welcome OFF-THREAD so Save/Load/Reset stay reachable immediately and the welcome streams in (genuine cancellation if the player acts first). Owner rulings: D-214-1=B (off-thread), D-214-2=yes (startup save `allow_compression=False`), D-214-3=yes (updatePlot legitimate/ungated — verify-only), D-214-4=A (separate non-input-blocking welcome status channel).

## Review scope (what to independently check)
1. **Architecture/concurrency correctness** of the off-thread design: single-game-thread state invariant (worker = provider I/O only; all `process_ai_response`/history/file mutation on the game thread); CR-1 (supersede at the SocketIO enqueue boundary `handle_user_input` before `user_input_queue.put`, not a game-thread line); CR-2 (history-version fence over the FROZEN request object, covering the first-iteration truncate/dedup at main.py:6706-7); CR-3 (worker sets its OWN `welcome_scope.quiescent` in a `finally` on all exits — the existing `close_live_turn_scope` only sets it for the global `_active_scope`; effective scope = `get_live_turn_scope() or get_active_welcome_scope()` at the gate web_interface.py:2592 + restore body 2664 + reset body 2709; `quiescent` set AFTER hand-back completes to avoid a torn-write / `os._exit` race).
2. **Fail-forward (B1/B2):** Load genuinely reachable during a slow/hung welcome; genuine cancellation (child reaped, not abandoned); NO new deadline (the live-path 600s watchdog is a REISSUE trigger, not terminal); the 180s kickoff-lease TTL (Task 1b) must not `stale_discarded` a completed slow welcome.
3. **Leanness / mechanism budget:** the only new mechanism is the D-214-4=A status channel (owner-mandated); everything else is reuse of `LiveTurnScope`/supersession + one optional `scope=` param on `call_live_provider`. Confirm no new store/WAL/persisted format/lock/deadline sneaks in.
4. **Provider/platform:** the openai SDK default ~600s timeout is terminal on the non-live path (why routing-through-live is required); no `max_tokens`; thin router untouched.
5. **Acceptance sufficiency:** the arms must be real native Windows, one op at a time, non-vacuous (slow non-thinking Gemma multi-minute for the cancellation/timeout arms), with on-disk + OS artifacts (PID-reap for cancellation; exactly-one-assistant-turn; CR-2 discard; per-op Save/Load/Reset; separate 180s + >600s reissue arms; #210 regression).

## Prohibitions (RESTATED — do not violate)
- Do NOT implement — this is a plan review. No production code from either agent until the owner approves post-review.
- `config.py` is gitignored; NEVER commit it. No voice/episodic work on this branch (that is a separate line). Tests stay LOCAL/untracked. ASCII-only in Python/console. No `git add -f`. No merge/PR/deploy.
- Commit/push only what the owner authorizes.

## Files the implementation will touch (allowlist for later)
`main.py`, `web/web_interface.py`, `utils/capture/live_provider_call.py` (one optional `scope=` param), a small frontend status channel (`web/templates/game_interface.html` and/or `web/frontend/src/**`), and ignored/local tests. NOT: provider router / `create_completion` / api_client response semantics, model registry, prompts, schemas, persistence, combat, the lease-state module's TTLs.

## Prior review state (for context; the panel is Claude's — review independently)
Claude ran a Part-3 blind panel (2 rounds + convergence recheck) that reached zero residual blocking findings. Do not defer to it — your independent pass is the point. Report any blocking design/concurrency/acceptance finding with a concrete failing input (R13); LGTM is a legal verdict (R14).

## Return
Your independent verdict on the converged plan (LGTM or blocking findings with file:line + concrete failing input), and confirmation you're ready to own native-Windows + Gemma acceptance once Claude implements. Per #193, review authorizes neither execution nor merge — the owner decides after your review.

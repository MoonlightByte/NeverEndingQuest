# TW-002 Wizard Silent-Recovery Plan

Status: PART-3 SIX-LENS CLEAN; OWNER GATES TW002-D6 AND TW002-R3 REMAIN OPEN.
No implementation is authorized by this file.

## Authority and evidence pin

- Owner mandate: `/mnt/c/agent-room-fleet-kit/local-data/tw002-fix-brief.md`, SHA-256
  `4c02f83417c7facadeebc21cbcec2b2733ef084f7c5979ebe5deea52aaae0fa0`.
- Governing authority: GitHub issue #193 v1.7, live `updatedAt`
  `2026-08-27T17:30:16Z`, read at session start. Relevant system pages are Part 2
  page 10 (unbounded work must not freeze the game thread; waits over roughly ten
  seconds show live status), page 11 (startup/character creation is a B1 play path;
  `create_completion` remains a thin router; real model/platform acceptance), and
  page 13 (real native headless/browser evidence, one acceptance operation at a
  time, gate-polarity negative controls).
- Dynamic branch pin: `fix/tw002-wizard-silent-recovery` starts from fetched
  `origin/integration/premerge-214-combat` at
  `dd73f94afceb1926cddadebf45250e1380ef25e9`. The integration branch is not edited.
  `origin/main` at `691b5a2f06b472e31c7a123964844d9506862535` is a verified ancestor
  of this candidate. Mainline remains the compatibility/design baseline; #214 is an
  unmerged candidate dependency supplied by the owner, not independent doctrine.
- Player promise advanced: README lines 82 and 360-362 say the game guides a new
  player through character creation. The wizard must not present a dead screen for
  ten-plus minutes when one provider connection stalls.

### Observed incident

Native-Windows Thornwood evidence under
`validation_evidence/thornwood_campaign/` records four real OpenAI wizard stalls.
The blocked T092 call reached `receive_response_headers.started` and then produced no
headers/body before the isolated process was terminated at about 651-657 seconds.
The repeated blocked request was the fifth/11-message T092 request, roughly 68-70K
characters, on `gpt-5.6-luna`, reasoning `none`, temperature `0.7`, without
`response_format`. The preceding request and larger combat requests completed.
The exact blocked payload later completed unchanged in 4.493 seconds from a fresh
diagnostic invocation; luna-low completed twice in 4.005-4.215 seconds. This proves
the production model binding need not change and that fresh reissue is a viable
recovery action. It does not prove whether the remote cause was connection-local or
queue-local.

### Code-proven failure path

- `utils/startup_wizard.py:1640-1724`: T092 freezes a deep-copied conversation,
  mutates live history only after usable content, then persists the accepted answer.
- `utils/startup_wizard.py:1761-1825`: T093 uses the same capture boundary and has a
  deterministic fallback for completed invalid/failed semantic output.
- `utils/capture/multi_model_capture.py:393-470`: without an active turn scope or
  explicit `_live_selected`, T092/T093 use the ordinary synchronous primary path.
- `core/ai/api_client.py:410-465`: no caller timeout means the SDK defaults remain;
  a caller-supplied transport trigger applies `max_retries=0` to prevent hidden SDK
  retries.
- `utils/capture/live_provider_call.py:468-619`: the existing #214 path freezes inputs,
  creates a spawned provider child, polls with ten-second callbacks, and reissues from
  a fresh process/connection. Its current parent watchdog is total elapsed, its
  repeated heartbeat text is deduped by native headless, and `_terminate_process`
  does not prove reap on every second-timeout/BaseException edge. T092/T093 are not in
  its reviewed allowlist and, without a scope, lifecycle commands cannot discover or
  cancel wizard provider work.

## Behavioral contract

| Existing behavior/goal | Disposition | Proof required |
| --- | --- | --- |
| Each accepted wizard answer is appended and saved exactly once. | PRESERVED | Reissue receives the same frozen messages; only the successful response reaches the existing append/save lines. Disk history contains one copy of every accepted player/assistant turn. |
| T092 keeps its canonical model/profile, prompt, temperature, response-format choice, capture, usage, and logging pipeline. | PRESERVED | Captured successful request/response metadata matches the normal path except invocation/correlation identity. |
| T092's existing three shared empty-response attempts per outer attempt are not lost by live selection. | PRESERVED/EXPANDED | Empty, timeout, connection, 408/409/429, and 5xx outcomes remain in required reissue and cannot reach the bounded outer counter. Deterministic 4xx/parameter disposition is owner decision TW002-D6. |
| T093 completed invalid JSON or deterministic provider error may still use its existing fallback after the current empty-response allowance. | PRESERVED | Separate negative controls prove empty-response retry and deterministic fallback; transport inactivity never becomes fallback. |
| A stalled OpenAI wizard transport may no longer freeze for the SDK's roughly 600-second default or terminate the wizard. | REPLACED BY OWNER MANDATE | A 40-second SDK read-inactivity trigger handles the observed no-bytes stall. A fixed 180-second high total backstop prevents a partial-body trickle from owning one generation forever. Either trigger makes the parent prove the child reaped and reissue the same logical call on a fresh child until success or genuine lifecycle cancellation; neither abandons or bounds the logical call. |
| Lifecycle controls that the active client actually exposes remain usable during a wizard call. | PRESERVED FROM THE CURRENT PREMERGE LIFECYCLE | Each OpenAI wizard semantic transaction uses the existing discoverable live scope through its canonical mutation boundary. Headless Save queues; headless Load/Reset/Quit and browser Exit/Quit can supersede and quiesce. Supersession bypasses T092 retry and T093 fallback. The pre-game browser does not expose Save/Load/Reset today; this narrow fix neither promises nor adds those controls. |
| Gemini, LM Studio, legacy, model registry, prompt/schema, and non-wizard callsites remain unchanged. | PRESERVED | Diff/callsite audit plus native normal-path evidence. |

No working branch, guard, or persisted field is deleted. GL-1 is therefore not
triggered by the intended change. If implementation changes this fact, stop and add
the full GL-1 origin/goal/disposition table before proceeding.

## Approach evaluation

### Approach A - explicitly route OpenAI T092/T093 through the #214 transport

Use the existing `capture_and_fanout -> call_live_provider` path with explicit
required selection at the two wizard callsites. Extend its reviewed task allowlist
and give the child a wizard-only 40-second HTTPX read-inactivity timeout with SDK
retries disabled. The parent has no low 40-second total-elapsed guillotine. It polls
and heartbeats until the child completes, returns a typed timeout/error envelope, is
genuinely superseded, or reaches the fixed 180-second high recovery backstop. Every
timeout/backstop generation is fully reaped before reissue.

The OpenAI SDK accepts a granular HTTPX timeout object and raises `APITimeoutError`;
HTTPX defines its read timeout as the maximum wait for a chunk of response data, not
total response duration. This supplies the required activity-aware seam without new
header IPC or changing Chat Completions response semantics:
`https://github.com/openai/openai-python#timeouts` and
`https://www.python-httpx.org/advanced/timeouts/`.

This is per-chunk inactivity, not a universal promise that every OpenAI generation
finishes within 40 seconds. The observed T092 profile is no-reasoning and its exact
69K-character request produced 241 output tokens in 4.493 seconds. That narrow evidence
puts healthy completion far inside the trigger; if this small call produces no response
data for over 40 seconds, the attempt is treated as stalled. A response that does
produce chunks keeps resetting the read clock and may finish well beyond 40 seconds.
The separate fixed 180-second total backstop covers the owner-ratified case where a
peer trickles partial bytes below the read-inactivity threshold but never finishes. It
is about forty times the observed healthy latency and is not the primary stall
detector. Exhaustion reissues rather than abandons.

Benefits:

- Reuses the only existing code-proven child-reap, fresh-process, correlation, usage,
  capture, backoff, and heartbeat lifecycle.
- Keeps the wizard's authoritative conversation append/save on its current thread;
  no new worker, store, lease, continuation, or persisted field.
- A 40-second trigger is below the mandated 60-second ceiling, about nine times the
  observed 4-4.5-second healthy request, and does not change the model.
- If the stall is connection-local, the first fresh child is expected to recover. If
  it is an OpenAI account/model queue event, fresh children may also stall; the same
  unbounded loop continues reaping and reissuing with visibly changing status until
  OpenAI recovers. A slow response that delivers data at intervals below 40 seconds
  may run past 40 seconds and finish normally. The mechanism and player contract do
  not depend on diagnosing the remote class. A pathological partial-body trickle can
  own one child only until its high backstop, after which the exact child is reaped
  and the logical call continues on a fresh connection.

Owner-accepted residual after the explicit Leanness tradeoff: a genuine T092/T093
response that takes longer than 180 seconds while continuously delivering chunks less
than 40 seconds apart would be reissued. No observed wizard call supports that class;
the exact no-reasoning 241-token call completed in 4.493 seconds, while the real defect
produced no response bytes for 600-plus seconds. This is a callsite-scoped,
evidence-calibrated safety judgment, not a universal provider-latency guarantee: for
this fast no-reasoning wizard call, a continuously progressing response beyond three
minutes is treated as negligible compared with the observed non-completing stall.
Adaptive threshold state and its sole artificial acceptance arm are therefore
rejected under AP-4/AP-5 and the narrow mandate.

Required narrow corrections to the shared helper: preserve the original exception
class/disposition in its primitive envelope; reissue timeout/connection/408/409/429/
5xx outcomes without bound; preserve T093's empty-response allowance and deterministic
fallback; and implement the owner-ratified TW002-D6 disposition for T092 deterministic
4xx/parameter errors. Classification uses exception types/status codes, never prose.
Every child lifecycle is enclosed by cleanup that does not return/reissue/propagate
until the exact child is observed reaped.

### Approach B - implement a wizard-local client loop

Add a T092/T093 helper in `startup_wizard.py` that creates a new client, supplies a
short SDK timeout, disables SDK retries, catches transport errors, and retries.

Rejected because a synchronous local loop cannot emit real heartbeats during the
attempt. Adding a heartbeat thread recreates cancellation and join/reap problems; a
subprocess recreates #214's existing mechanism. Reusing the thin client directly also
risks bypassing capture/usage/correlation behavior or duplicating it. Approach B is
not smaller once the full B2 cancellation and player-status contract is included.

Decision TW002-D1: choose Approach A. This is an owner-mandated repair to the observed
T092/T093 path, not a general provider-routing redesign.

## Scope and file allowlist

Expected production files:

1. `utils/startup_wizard.py` - explicitly select the reviewed required live transport
   only for OpenAI T092 and T093; open/close the existing discoverable live scope for
   each complete semantic transaction through its canonical write; propagate
   supersession past T092 retry and T093 fallback;
   preserve request construction, conversation mutation, persistence, and fallback.
2. `utils/capture/live_provider_call.py` - add T092/T093 to the reviewed wizard task
   set; give only those tasks the 40-second SDK read-inactivity trigger; add structured
   child-side disposition; make reap unconditional; produce changing wizard heartbeat
   text; retain existing policy/timeout behavior for every other task ID.

`utils/capture/multi_model_capture.py` and `core/ai/api_client.py` are inspection-only
unless the panel proves the existing explicit selection/timeout plumbing cannot carry
the contract. Any expansion returns to plan review before editing. Not in scope:
model bindings, prompts, schemas, saved-state formats, web UI, combat, startup welcome,
or other callsites.

## Implementation slices

### Slice 1 - transport policy without behavior expansion

1. Add T092/T093 to an explicit wizard-required task set inside
   `live_provider_call.py`; keep the existing required/advisory sets and all other
   task classifications unchanged.
2. For T092/T093 construct a granular SDK/HTTPX timeout whose read-inactivity value is
   40 seconds and disable SDK retries. Do not apply 40 seconds to the parent's total
   poll duration. Add a fixed wizard-only 180-second parent recovery backstop per
   child generation. Exhaustion reaps and reissues rather than returning or
   abandoning. Do not add adaptive threshold state or a terminal retry counter. Keep
   all other tasks on their existing 600-second policy unchanged.
3. Add structured child disposition/original exception class to the primitive envelope.
   Timeout/connection/408/409/429/5xx are retryable provider availability. T093 keeps
   its current empty-response allowance before deterministic fallback. T092 follows
   TW002-D6 for deterministic 4xx/parameter outcomes. Never classify exception prose.
4. Put the Popen/poll/status path inside `try/finally`. Terminate, then kill when needed,
   and continue waiting/polling until `process.poll()` proves the exact child exited;
   close every stream on every `BaseException`. Cleanup failures never enter the
   wizard semantic counter and no later generation starts before observed reap.
5. Preserve operation/generation correlation, usage identity, and retry-after/backoff.
   Wizard heartbeat content must change at each roughly ten-second emission (for
   example cumulative elapsed time) so native headless cannot dedupe a live wait.

### Slice 2 - wizard opt-in and state preservation

1. At T092 and T093, pass explicit required live selection only when the snapshotted
   provider is OpenAI. Other providers remain on their existing path.
2. Open the existing global `LiveTurnScope` for exactly one wizard semantic
   transaction and finish/abort it on every exit. For T092, the scope remains active
   through the accepted assistant append and startup-history persistence. For T093,
   it remains active through `update_party_tracker`'s successful canonical write.
   Revalidate the live claim immediately before those mutations: superseded work
   mutates nothing, while a mutation already admitted at the boundary completes
   atomically before the scope becomes quiescent. This makes headless Save queue until
   the durable boundary; makes headless Load/Reset/Quit and browser Exit/Quit
   supersession discoverable through existing consumers; and requires no new registry,
   UI control, or persisted state. A
   `LiveProviderSuperseded` exception is re-raised past T092's generic retry, T093's
   generic fallback, and the startup wrapper.
3. Keep the same deep-copied request across every transport generation. Do not append
   the player's input, assistant output, or any retry note during transport recovery.
4. On success, execute the existing one-time append/save/parse flow. T093 invalid JSON
   remains a completed semantic result and retains its deterministic fallback.
5. Emit wizard-specific changing presentational text through the existing status
   manager. No provider error, generation count, or retry mechanics become assistant
   narration or conversation history.

### Slice 3 - mandatory simplifier and static verification

1. Remove any duplicate wrapper, generic configuration knob, or second retry counter
   introduced during implementation. The final mechanism must remain the existing
   child lifecycle plus a task-local trigger/classification.
2. Run `git diff --check`, ASCII scan on added lines, `py_compile` for changed/importing
   files, import smoke, FS-1 grep, task-ID/caller inventory, and targeted deterministic
   I/O checks as development aids only.
3. Confirm no tracked test or evidence artifact is added and no unrelated file changes.

## FS-1 limits classification

The planned diff intentionally contains `timeout`, `max_retries=0`, and a 40-second
numeric trigger.

| Limit | Exhaustion path | Verdict |
| --- | --- | --- |
| Wizard SDK read-inactivity trigger (40 seconds) | SDK returns typed timeout only after no response data arrives for 40 seconds. Parent observes/reaps the child, then starts the next generation with the same frozen logical request. Active data resets this read clock; this trigger does not impose a 40-second total cap. | CONTINUES under B2-iii. |
| Wizard active-progress backstop (fixed 180 seconds per generation) | A child that trickles partial bytes without ever completing is terminated, proven reaped, and reissued with the same frozen request. The logical call and heartbeat continue without a retry ceiling. | CONTINUES under B2-iii; high recovery backstop, not a terminal deadline. Owner accepts the callsite-scoped residual described above; this is not asserted as universal safety. |
| SDK `max_retries=0` on the child attempt | Prevents hidden retries on the same SDK client/pool; the parent owns visible fresh-process reissue. | CONTINUES under B2-iii. |
| Existing T092 `STARTUP_AI_MAX_ATTEMPTS=3` | Healable OpenAI availability/empty outcomes can no longer exhaust it. Deterministic 4xx/parameter behavior awaits TW002-D6. | OPEN OWNER DECISION. |
| Existing shared empty-response attempts (3) | Live selection must not reduce T093's allowance; T092 availability remains required until success/cancellation. | INHERITED, PRESERVED. |
| Existing T093 fallback | Completed deterministic/invalid output still moves startup forward after preserved allowance. | INHERITED, PRESERVED. |

Any implementation branch where read-inactivity exhaustion terminates the logical call,
returns T093 fallback, abandons a live child, or reaches T092's bounded semantic counter
for a healable class is a CRITICAL failure.

## Acceptance plan

Acceptance runs one operation at a time from an isolated, freshly copied,
startup-required native-Windows game directory through
`run_headless.py serve`, optionally driven by `HeadlessClient`, using the configured
real OpenAI model. Local deterministic checks do not accept player experience.

### A1 - induced response-header stall, then real recovery

Use the owner-authorized local transport proxy technique: the first two selected
OpenAI wizard generations are accepted and their response headers are withheld. After
the code closes and reaps each exact stalled connection/child, generation three is
forwarded to real OpenAI. Drive genuine character creation one player answer at a
time.

Required evidence:

- trigger fires in under 60 seconds;
- each stalled child PID/connection is closed and reaped before its successor starts;
- generations two and three use the identical model, prompt/messages, temperature,
  and response format with new correlation generations and fresh connections;
- real OpenAI returns the completion and character creation continues through T093;
- complete player-visible NDJSON/transcript shows changing setup heartbeat at roughly
  ten-second intervals across at least two fully stalled generations, reissue/backoff,
  and eventual real recovery, with no
  error, fallback, duplicate question, duplicate answer, or dead screen;
- the exact new `startup_conversation_archive_*.json` created by the run contains each
  accepted user and assistant turn exactly once; the active
  `modules/conversation_history/startup_conversation.json` is absent after successful
  cleanup; final canonical character/party files prove setup completed.

This is the gate-polarity firing-path proof. A proxy-generated model response is
forbidden; the successful response must come from real OpenAI.

### A2 - normal-path negative control

Run a separate fresh native-Windows character creation directly against real OpenAI,
with no induced fault. Require full completion, no reissue marker, no duplicate
history, the same canonical T092/T093 model/profile/request shapes, and normal
player-visible pacing. Record real per-call latency/tokens and compare with the
pre-change healthy 4-4.5-second evidence; do not claim statistical equivalence from
one sample, but reject any new fixed delay or extra provider call on the success path.

### A2b - slow-but-progressing response polarity

In a separate run, the proxy forwards one authentic real-OpenAI response without
altering its content but paces response-body chunks so total duration exceeds 40
seconds but remains below 180 seconds, while every inter-chunk inactivity interval
remains below 40 seconds. Require exactly one child generation/provider request, no
timeout/reissue marker, successful completion, and exact-once archived
conversation/disk state. Record header/chunk timestamps. This proves the primary
trigger is read inactivity rather than a low total-elapsed guillotine.

### A2c - partial-body trickle backstop polarity

In a separate proxy run, start an authentic OpenAI response but hold it in an
incomplete partial-body state while emitting transport bytes often enough to avoid
the 40-second read-inactivity trigger. Require the initial 180-second backstop to fire, the
exact child/connection to be reaped, and the next fresh generation to complete from
real OpenAI with the identical frozen request. Player-visible heartbeat must remain
live; no partial response enters history. This adversarial control proves the high
backstop continues recovery and never abandons the logical call.

### A3 - completed-error polarity

Run sequential, separately recorded boundary probes without fabricated player/model
responses: (a) a typed timeout/connection envelope and a completed 429/5xx envelope
enter required reissue; (b) T093 receives three structured empty completions before its
fallback and a separate deterministic 400 envelope reaches fallback; (c) T092's
deterministic 400/parameter probe follows the owner-ratified TW002-D6 disposition.
Each probe records exact structured status/cause/disposition. These are deterministic
boundary checks, not gameplay acceptance.

### A3b - lifecycle cancellation and Save queue

On separate induced-stall runs, issue Save, Load, Reset, and Quit one at a time through
the real headless command surface. Save must be accepted/queued and complete only
after the safe boundary. Inspect its authoritative files: a T092 Save contains the
single accepted assistant/history turn, and a T093 Save contains the selected
character/module/world-location party state; neither may capture the pre-transaction
state while live setup has advanced. Load/Reset/Quit must supersede, prove the child
reaped and scope quiescent, mutate no superseded wizard result, and never hit the
busy-refusal branch, T092 retry, or T093 fallback. Use a known-valid Save folder for
Load and the real confirmed Reset command so invalid arguments cannot satisfy the
control assertion.

### A3c - browser control and status truth

In a separate native-Windows browser/Playwright setup run, induce the same T092 stall.
Require changing player-visible setup status and the existing Exit/Quit control to
supersede, reap, and quiesce without a dead screen or provider error. Confirm the
pre-game browser still does not advertise Save/Load/Reset; those controls are outside
this narrow fix rather than silently promised by backend capability.

### A4 - cleanup and platform evidence

Confirm native Windows handle/process cleanup, zero orphan provider children, no
secret-bearing evidence, clean port/process teardown, and unchanged tracked tests.
Record commands, raw timestamps, PIDs/correlation generations, full player output,
and before/after authoritative files. Verdicts are PASSED/FAILED/BLOCKED/NOT-REACHED.

## Six-lens Part-3 review dispatch

This plan is FULL because it touches provider routing/threading and adds a numeric
transport trigger. Dispatch six blind reviewers against this exact file and resolution
ledger:

1. Architecture Custodian.
2. Fail-Forward DA, including FS-1.
3. Acceptance DA.
4. Consumer/Compat DA.
5. Player-Experience DA.
6. Leanness DA.

Every blocking finding requires a concrete failing sequence/state. The controller is
the sole plan writer, incorporates accepted findings, and redispatches all six until
one clean confirmation pass. Convergence authorizes neither implementation nor merge;
Claude's independent review and explicit owner implementation approval remain required.

## Tracked follow-ups

- No additional same-class naked play-path caller has yet been established by evidence.
  The repository inventory found a raw SDK connectivity call in
  `web/web_interface.py`, but it is not the wizard and has not been shown to share the
  gameplay-freeze mechanism. Creating speculative work would violate AP-4. If the
  implementation audit establishes another gameplay-reachable caller with the same
  unbounded/no-heartbeat path, file a separate GitHub issue in that same turn and do
  not modify it here.
- No prior document is superseded. The #214 plan is historical provenance for the
  candidate helper; this plan narrows only T092/T093 behavior and leaves all existing
  #214 task policies unchanged.

## Resolution ledger

| ID | Finding/decision | Resolution | Status |
| --- | --- | --- | --- |
| TW002-D1 | Choose #214 reuse or wizard-local duplicate. | Approach A; existing child lifecycle is the smaller complete B2 mechanism. | RESOLVED by owner mandate plus code trace. |
| TW002-D2 | Stall trigger cadence. | 40-second SDK/HTTPX read inactivity is primary; about 9x measured healthy latency. Slow active bodies continue past 40 seconds. A fixed 180-second per-generation backstop reaps/reissues partial-body trickles without bounding the logical call. The owner accepts the documented negligible residual rather than adding adaptive state for an unobserved class. | RESOLVED by owner evidence synthesis, Leanness ruling, and official SDK/HTTPX contract. |
| TW002-D3 | Provider scope. | OpenAI T092/T093 only; other providers are unobserved working paths and remain byte-identical. | RESOLVED under AP-5. |
| TW002-D4 | Error classes. | Child emits structured cause/disposition. Timeout/connection/408/409/429/5xx are healable required reissue. T093 preserves empty allowance/fallback. T092 deterministic class awaits D6. | PARTIAL - D6 open. |
| TW002-D5 | Model swap. | None. The unchanged luna-none payload completed in 4.493 seconds; changing quality/cost is neither necessary nor authorized. | RESOLVED by real-call evidence. |
| TW002-D6 | T092 deterministic OpenAI 4xx/parameter outcome. | Owner must ratify inherited bounded failure plus a separate recovery-UX issue, or authorize a broader live configuration-correction scene. Agents cannot create a B2-iv ruling. | OPEN - blocks convergence/implementation. |
| TW002-R1 | Part-3 six-lens convergence. | Architecture, Fail-Forward/FS-1, Acceptance, Consumer/Compat, Player Experience, and Leanness all returned CLEAN on the same substantive plan SHA `a501b75a4456f65986550186e5d981178ffc49a41cb6fe45cab60c1480e16bd8`. The ledger-stamped hash receives a final no-substantive-change confirmation. | CLEAN; ledger-hash confirmation pending. |
| TW002-R2 | Claude independent review. | Claude approved SHA f8c4d28f subject to wave-1 refinements now incorporated. Re-review updated SHA after convergence edits. | IN PROGRESS. |
| TW002-R3 | Owner execution approval after convergence. | Required by #193. | OPEN - blocks implementation. |

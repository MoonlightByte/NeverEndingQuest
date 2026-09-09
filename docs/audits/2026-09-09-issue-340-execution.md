# 340 execution and acceptance

2026-09-09. Candidate tested in fix/340-console-stream at
/home/loup/neq-worktrees/340-console-stream. Base 99fe2078; revisions are evidence
only. Owner authorized implementation/testing, recorded live #193 D-340-1.
Publication remains separate D340-2. No commit, push or merge performed.
Approved plan SHA256 1cdf2b4493c09c0469f058dfe86c62e199dea90ac554cf20149550064a57dd2c.
Its frozen PLAN ONLY wording records the earlier review stage; D-340-1 supersedes
that execution hold without changing the reviewed mechanics.

## Implementation and focused gates

Only production change: utils/encoding_utils.py, +5/-12. Configure Python's
original physical Windows streams in place; retain active capture routes and
strict UTF-8. No gameplay, model, schema, state writer, lock or retry changes.
Candidate SHA256 2638652b31f65180b29f55809a821de81d570a05388d3575bc3d1172eae783ad.
Both architecture pages have narrow flow notes; older anchors are not recertified.

Independent actual-diff simplifier/compatibility review: PASSED, no findings.
Every byte outside the two approved replacements preserved. LF-only file:
baseline 298 LF/0 CRLF; candidate 291 LF/0 CRLF. ASCII additions only.
Native Python3.12 and WSL Python3 py_compile PASSED; git diff --check empty.
Pyflakes: zero undefined names and zero introduced warnings. The existing unused
Optional import and two duplicate-key warnings are unchanged (line offsets -1).

Minimum No-Limits scan of actual production diff and full touched Python file:
`grep -nE '\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat'`
Raw output: EMPTY (both).
Minimum Single-Path scan of actual production diff and full touched Python file:
`grep -nE 'legacy|use_new|_v2\b|mode ?==|if .*provider ?==|fallback'`
Raw output: EMPTY (both).
Caller-family `rg -n 'setup_utf8_console\(' --glob '*.py'` raw output:
```
main.py:10553:    setup_utf8_console()
utils/encoding_utils.py:284:def setup_utf8_console():
```
No new public symbol, timeout, store, or alternate route.

## Fixture and evidence provenance

Evidence root: /mnt/c/340-evidence-Vkg08O (private, local, not tracked).
Native source: /mnt/c/336-src-NfwED7, reused to avoid another large export.
An exhaustive tracked non-doc baseline comparison found ZERO mismatches to
99fe2078 except the intentionally overlaid encoding_utils.py. Overlay matches
candidate SHA above. Fresh game folders use product prepare_game_dir with the
official checked-in The_Thornwood_Watch module; no game-state edits or fake calls.
All game prompt files byte-match source. Private config never printed or tracked.
Effective provider OpenAI; native interpreter C:/Python312/python.exe 3.12.3.
Browser source is a copy of this candidate; explicit supported --ui legacy smoke.
No claim of a fresh React-specific run or a complete campaign playthrough.

| Arm | Actual fixture | Final verdict | Evidence relative to root |
| --- | --- | --- | --- |
| D2 OS I/O primitives | native Python, io_check.py | PASSED | io-stdout.log, io-stderr.log |
| A1 Windows terminal | C:/340-game-G5dZ2Q | PASSED | A1-native.log, A1-restart.log |
| A2 Windows redirected stdout/stderr + EOF | C:/340-pipe-AVzOLS | PASSED | A2-stdout.log, A2-stderr.log |
| A3 native headless menu + Quit | C:/340-headless-JcJbye | PASSED | A3-headless/protocol.ndjson, stderr.log |
| A3 browser menu + Exit | C:/340-web-z62iTO | PASSED | A3-browser-menu.txt/.png, A3-browser-exit.txt/.png, A3-browser-events.json |
| A4 WSL terminal menu + Ctrl-C | /mnt/c/340-pipe-AVzOLS | PASSED | A4-posix.log |

D2 exercises actual helper with real Windows OS-redirected text streams, repeated
configuration, identity/no-close assertions, None/non-reconfigurable original
stdout and independent stderr. Escaped non-ASCII output round-trips as UTF-8 on
both streams. No game function, model response or UI stub used.

A1 actual main.py reaches the original failing welcome boundary, real module menu,
ordinary input `1`, accepted interview, then Ctrl-C exits 0. Restart resumes the
interview without reselecting the module; Ctrl-C again exits 0. Raw screenshots
are not substituted for logs: script captures include native terminal controls.
Verbatim final visible line on both runs:
`Dungeon Master: Setup paused. Your choices are retained.`
Startup conversation remains on disk; no incomplete party_tracker is published.

A2 actual main.py uses OS redirection and /dev/null stdin, not a replacement
Python stream. Reaches real menu, EOF yields the same neutral pause, exit 0.
Both stdout/stderr decode strictly as UTF-8; no write/flush exceptions.

A3 headless emits 45 strictly increasing sequenced protocol records, all JSON.
Quit 340-A3-quit: received/result ok/status Quit complete/neutral pause/exit
player_exit all at ts1788986586.600; native process exit0 observed1788986586.710.
No stdout contamination. Native relay was closed with console EOF after exit.

A3 browser sends actual start_game at1788986765317ms; the real module menu is
captured in full. Exit via browser button sends user_exit at1788986769815ms;
server exit_acknowledged at1788986769819ms (4ms). Browser displays verbatim:
`Thank you for playing!`
`You can now safely close this browser tab.`
The server intentionally remains alive after browser Exit; after acknowledgment
its owned launcher34316/server5456 tree was stopped for fixture cleanup. This is
not presented as a naturally exiting server process. No model call remained.

Harness false starts, retained not hidden: initial URL8357 was wrong for config's
8358; then Start clicked before connection sent NO start_game (captured in
A3-browser-premature-click-events.json). Corrected browser-only wait for actual
connection, no product changes; rerun sends the real Start and Exit above.

A4 menu+Ctrl-C exits0 with the neutral pause. Runs after browser server cleanup;
all gameplay probes serial. POSIX helper remains a code-proven no-op.

## Per-call evidence and limits

Each fixture's debug/api_captures/api_calls_master.jsonl is the raw source.
All are T092, captured model gpt-5.6-luna, provider openai, disposition success.
The raw response object exposes content, NOT response.model; no assertion that
the captured binding label independently proves the provider response model ID.
Parsed request keys are messages/message_count. The feature under test is stream
delivery, not a new prompt field; player text is the consumer proof.

| Arm / master line | Provider seconds | Role |
| --- | --- | --- |
| A1 1 | 4.578 | Module menu |
| A1 2 | 3.765 | Character catalog |
| A1 3 | 4.906 | Interview author |
| A1 4 | 3.500 | Interview review, accepted true |
| A1 restart 5 | 4.657 | Resumed interview author |
| A1 restart 6 | 4.156 | Resumed interview review, accepted true |
| A2 1 | 3.469 | Module menu |
| A3 headless 1 | 3.625 | Module menu |
| A3 browser 1 | 3.985 | Module menu |
| A4 (A2 fixture master line 2) | 3.544 | WSL module menu |
| A2 repeat (shared master line 3) | 3.609 | Redirected module menu |

Native terminal input timestamps were not independently instrumented: provider
seconds are NOT input-to-output timings. Browser Start-to-capture is approximately
4.29s; browser Exit acknowledgment 4ms. Headless prompt ts1788986559.582.
Generation2 in A1 is the separate existing semantic review within its scope, NOT
a transport retry; both reviews accepted true. No model-quality or speed claim.
The full verbatim menu/interview text lives in raw logs and disk startup history.

Independent audit requested durable command/exit evidence. COMMANDS.md records
the executed commands; manifest.json records baseline comparison and prompt
hashes. A2 repeat through redirect_receipt.py again exits0, receipt includes exact
command/start/end: 1788986997.373 to1788987002.975 (5.60s whole process). Original
A2 evidence is retained. No code change or substitute model used for that repeat.

## Boundaries and remaining authorization

Lifecycle/error scan over A1/restart, A2 stdout/stderr, A3 headless protocol/stderr,
A3 server, A4, and A2-confirm stdout/stderr:
`rg -n "Traceback|UnicodeEncodeError|object has no attribute '(write|flush)'|Startup wizard failed|LIVE_PROVIDER_REISSUE|completed_invalid|stale_rejected"`
Raw output EMPTY (exit1). Matching error/degrade/reissue/stale events: zero.
All 11 captured calls including A2 repeat have success disposition; the two
interview reviews accepted true. No invalid/omitted feature event observed.
Final native process scan at2026-09-09T13:51:35-07:00: remaining=[]; POSIX main
process scan empty. Evidence final-native-processes.json. Owned test servers and
relays are stopped; no cleanup of user data was performed.

#341 Reset wording and #338 unavailable character selection stay separate.
No full combat, Save/Load, schema, model quality or React recertification claimed.
No unrelated fixes.

## Final independent reviews

Actual-diff Fail-Forward and both sentinel review: PASSED, empty raw scans,
no new failure swallowing or parallel route. Candidate hash unchanged.
Independent non-author five-point/PX audit: PASSED for owner presentation:

1. Spec coverage: candidate complete, exact one-file edit; landed-commit check
   pending publication authority, not misrepresented as committed.
2. Ledger closure: candidate tasks complete; D-340-1 closed, D340-2 owner-open.
3. Follow-ups: live #338/#341 still open and accurate; no new product finding.
4. Falsifiers: compilation, warning delta, bytes, callers, prompt equality and
   both raw sentinel scans independently rerun, PASSED.
5. Bug-layer acceptance/PX: raw terminal/headless/browser text, PNGs, state and
   all11 call responses independently read; all planned narrow arms PASSED.

Reviewer independently confirmed zero native-source differences across1803
non-doc/non-Markdown files and27 prompts per fixture. Controller archive manifest
also includes non-doc Markdown and counts1823 files; both report zero differences.
No remaining in-scope implementation or test work identified. Publication audit
must verify the eventual commit contains this exact accepted candidate.

Commit/push/merge/issue closure wait for owner publication approval D340-2.

## Publication authorization (2026-09-09)

The owner subsequently cleared commit/push to main; live #193 D-340-2 records
the ruling. Main remains at the tested base99fe2078, so no integration conflict
or untested product delta is introduced. Publish this exact accepted candidate
and documentation by fast-forward. Earlier pending statements are chronological
evidence of the separate execution and publication gates, now resolved.

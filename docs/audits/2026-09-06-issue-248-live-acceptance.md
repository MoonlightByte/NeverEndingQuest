# Issue 248 live acceptance record

Product candidate: d61f20d317f675508930ab973ca5498da44361f8.
Baseline: 185f8997a5055521f04fe7a55ca908a41f0d412f.
Isolated branch: fix/248-pre-input-travel-recovery. No merge or push.

Owner explicitly directed unrelated findings to remain separate and testing to
continue. No production changes were made during these acceptance runs. This
record supersedes the earlier pause awaiting disposition of narration issue312.

## Result boundary

The reached recovery, control, input-ordering and normal-startup checks passed.
There is no observed new in-scope248 failure in those checks. This is NOT an
all-branches/full-matrix PASS: conditional failure paths and some exact provider
cancellation stages remain unproved below. Initial narration errors are recorded
as errors, not relabeled as correct because recovery mechanics passed.

All live calls used real OpenAI with the configured production routing unchanged.
No synthetic provider/checkpoint injection or gameplay-state edits. Crashes were
actual process termination after observing naturally created pending records;
recovery used the original game path. Local test observers drove real controls.

Private evidence root: /mnt/c/agent-room-fleet-kit/local-data/248-evidence/.
Raw transcripts/captures remain local, outside Git. ACCEPTANCE_PROGRESS.md and
native/NATIVE_REPORT.md give detailed receipts, IDs, mistakes and timestamps.

## Reached acceptance

| Check | Verdict | Evidence relative to root |
|---|---|---|
| A1 WSL within-module restart, no wake input | PASS mechanics/order: T013/T063/T064, arrival72 before prompt123, A02/09:05 once, journal1 | a1-restart/protocol.ndjson; a1-before; a1-after |
| A1 native Windows, repeated real journey | PASS mechanics/order twice at original C:/248n-a1; genuine next-prompt solo correction accepted | native/NATIVE_REPORT.md; native/a1-resume; native/recovery-quit |
| A2 cross-module restart | PASS: Keep/A02 -> Thornwood/RO01, 240min09:05->13:05 once; arrival80 before prompt133, no redundant welcome; one source archive/completion | a2-crossmodule-before; a2-crossmodule-after; a2-crossmodule-restart |
| A3 waiting Save | PASS: accepted66, arrival92, saved163 with correct A02/09:15 and journal3 | a3-save-recovery-committed/protocol.ndjson |
| A3 Load and waiting-Save cancellation | PASS: deferredSave25, validatedLoad44, cancelledSave46 naming controlID, selected_applied64, restart66; relaunch proves selectedA02/09:05 | a3-load2-recovery; a3-load2-relaunch |
| A3 native Save -> Quit | PASS pre-provider boundary: exactly one cancelledSave naming Quit; zero new narration/prompt/snapshot; pending bytes retained, exit0 | native/recovery-quit-observed; native/quit-preserved |
| A3 active provider-child -> Save -> Quit (WSL) | PASS: real child with owned established TCP observed, child still alive at Quit, deferredSave cancelled43 naming Quit, exit44/serve0, child gone, pending/party/journal unchanged | a3-provider-quit-crash; a3-provider-quit-recovery/protocol.ndjson |
| A3 native browser Reset | PASS control/disk boundary: disabled input explains recovery, Load/Reset enabled, wrong confirmation code rejected, confirmed Reset applies, backup retained, no new stale arrival | browser-reset-retry/observations.ndjson; recovery-controls.png; after-disk |
| A4 early input during restarted recovery | PASS reached queue boundary: accepted20 -> arrival55 -> prompt106 -> distinct action199 -> prompt279; input occurs once in history and T067 | a4-queued-before; a4-queued-restart; a4-queued-after |
| A5 no-pending startup | PASS existing asynchronous welcome/readiness and normal Quit | a5-startup; native/a1-initial; a3-load2-relaunch |
| A5 ordinary uninterrupted travel | PASS existing three-call chain673/676/681 -> arrival691 -> prompt73909:10 | a1-restart/protocol.ndjson |
| A5 authentic saved combat | PASS: TW05-E1 round5 returns narration148/prompt196; party and encounter byte-identical; clean Quit | a5-saved-combat; a5-saved-combat-baseline |
| A6 legitimately retired uncommitted residue | PASS observed last-clean-state behavior only; not retained-conflict coverage | a3-save-before; a3-save-recovery |

The saved-combat fixture was an unchanged copy of the authentic #275 W3 game,
whose party construction was owner-authorized and whose encounter arose through
normal play. Static prompts/schemas came from the tested revision. No new battle,
level-up or full combat-system acceptance is claimed. Candidate and matched
complete-source baseline each made exactly one T043 resume call, returned the
same round/player state, and left party/encounter bytes unchanged. T043 measured
3.022s candidate and2.678s baseline: a single sample, not a performance claim.

Native runtime was C:/Python312/python.exe, actual win32, not a WSL imitation.
Browser used actual production Flask/SocketIO and React UI, controlled by
Playwright. Its collection-only launcher was not supervised: Reset terminated
the server and cleared state, but automatic reconnect/new-wizard UX is NOT proved.
The old arrival visible on the page was explicitly Previous Session Messages,
not a new post-cancellation publication. Independent reviewer checked the image.

## Measured recovery calls

Capture labels identify selected gpt-5.6-luna, OpenAI; actual response.model is
UNKNOWN where the recorder does not retain it. Durations are measured capture
latencies, not estimates from adjacent completion timestamps.

| Run | T013 | T063 | T064 | Other |
|---|---:|---:|---:|---|
| Native repeated A1 | 3.052s | 4.816s | 5.055s | no redundant welcome |
| A2 cross-module | 2.365s | 3.765s | 3.731s | T03820.236s; T0398.095s |
| A4 restarted recovery | 1.828s | 4.632s | 4.147s | subsequent queued T0674.711s/T0655.718s |

## Separate findings and imperfect attempts

- #312: initial arrival may misidentify solo Rowan or use morning/twilight at
  the wrong canonical time. Real corrections were accepted in nativeA1 and
  A2; this does not retroactively make the initial narration truthful. The
  baseline request chain is unchanged by248. No prompt repair absorbed.
- #311: existing undefined inputs skip module-final T108. That consumer's
  cancellation coverage remains NOT-REACHED, not covered by transition T108.
- #213: repeated chronicle-compression failure diagnostics persisted after
  successful recovery (A2 six, A4 one). Original source is retained; no full
  memory/zero-error claim. Existing unchanged parallel compressor; additional
  evidence posted to issue213, exact underlying cause not newly established.
- #314: inherited frontend dependency audit findings, no dependency repair.
- #315: two inherited HeaderBar test assertions fail on both candidate/baseline.
- Existing T039 invalid-export fallback and solo episode_no_witnesses advisory
  are recorded; zero protocol-error events does NOT mean zero logged warnings.

Missed-timing control attempts, invalid absolute Save-folder input, initial
browser placeholder mismatch and incomplete baseline export are retained as
NOT-REACHED/setup-invalid. They are not counted as successful acceptance. The
corrected browser observer matched the real full status string. One Barracks
request named an absent location and was correctly rejected by the current atlas;
the player then chose an offered location. No state repair or prompt-shopping.

## Development checks

Ten-file py_compile, import smoke, diff whitespace, pure Save queue/cancellation
checks and independent post-code diff/sentinel reviews passed. Frontend tsc-b and
Vite production build passed. Candidate and complete-source baseline each had
344 passing and2 failing tests, the same #315 assertions. No tracked tests changed.
The initial frontend-only baseline export lacked required Python source and is
explicitly invalid as a comparison; the complete-source rerun is authoritative.
Known baseline undefined-name findings311 prevent an all-clean pyflakes claim.

## Unproved conditional branches and release boundary

- Actual child lifetime/reap is proved on WSL: child3693812 observed with an
  established connection at1788747078.486, alive at Quit1788747078.553, absent
  at clean process terminal1788747078.907. No new narration or prompt. Exact
  T013/T063/T064 task-stage attribution remains UNKNOWN: parent-stack capture
  was denied, so no specific provider-frame or Windows mid-child claim is made.
- A4 surviving-process interrupted continuation and final Save/exit siblings:
  NOT-REACHED. Restarted queue acceptance does not establish these paths.
- A6 authentic retained conflicts, failed-vs-blocked ordered intents at boot,
  raw-terminal numbered Load/confirmed Reset/Quit: NOT-REACHED. No corrupted
  checkpoint or fabricated provider outcome was manufactured to force them.
- T027, transition T108 and module-final T108 cancellation: separate unproved
  consumers. One successful recovery does not prove their cancellation stages.
- Browser automatic restart/reconnect, hidden-tab completion and Save->Reset
  cancellation are not inferred from the confirmed Reset disk terminal.

Independent read-only reviewers separately verified native/browser controls and
A2/A4 protocol, disk and player-truth claims. Their verdicts explicitly retain
the above limits. Owner retains merge/release authority; no merge performed.

All acceptance games/relays/provider children were shut down after these runs.
The original248a1 test fixture intentionally retains the final authentic pending
journey after accepted Quit; it is evidence, not an orphaned running game.

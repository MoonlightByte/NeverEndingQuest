# Issue 248 post-code review (acceptance still pending)

Candidate: fix/248-pre-input-travel-recovery, product baseline185f8997,
docs baseline9008f498. Ten Python files; no schema, prompt or model edits.
Independent reviewers are read-only; controller alone writes and runs gameplay.
This records code-review dispositions, not approval to merge.

## Full diff / simplifier: c3_scope_diff

LGTM after five concrete corrections and final publication-only followup:
- Recheck captured authority after successful scope finish/Save drain.
- Cross-root entry, post-T064 and pre-publication authority checks.
- Suppress queued acknowledgment after synchronous Save cancellation.
- Omit welcome only when this recovery actually published arrival.
- Preserve cancelled borrowed scope purpose for delayed Save admission.
- Carry local publication observation across cleanup-only retries, setting it
  after actual display and before checkpoint writes. No persisted field/store.

Simplifier: preserve existing continuation/controls; no lifecycle framework or
extra provider work. The small extracted terminal menu is shared, not duplicated.

## No-Limits: c3_nolimits_postcode

LGTM for this sentinel only. Raw commands included:

```text
git diff --unified=0 -- '*.py' | rg -n '^\+.*(timeout|deadline|max[_ -]?(retries|attempts|tokens)|retry[_ -]?(limit|budget)|abandon|fallback|fail.open|fail.closed|elapsed|monotonic|sleep|_interruptible_wait|cancel|legacy|limit|budget)'
rg -n -i 'timeout|deadline|max[_ -]?(retries|attempts|tokens)|retry[_ -]?(limit|budget)|abandon|fallback|fail.open|fail.closed|elapsed|monotonic|sleep|_interruptible_wait' <all ten Python files>
git diff --unified=0 -- utils/capture/live_provider_call.py | rg '^@@'
```

Material hits: main7348/7352 monotonic/elapsed display only; 7350/7442/7455/7693
existing0.5s interruptible waits inside unbounded loops. No count/deadline terminal.
live_provider_call518 fault/elapsed cannot cancel Save; actual accepted control
is required. Provider diff ends in Save queue/drain, not provider execution.
Location summarizer573 max_retries3 and700 delay/704 exhausted error inherited;
only typed cancellation rethrow changes. Two added legacy-effects comments are
moved old lines. Other full-file deadlines/fallbacks unchanged, not re-ratified.

## Single-Path: c3_singlepath_postcode

LGTM for this sentinel only. Read full product diff against185f8997, approved
plan, progress and exact surrounding startup/control/receipt code. Raw scans:

```text
git diff 185f8997 -- '*.py'
git diff 185f8997 --numstat
rg -n 'Thread|Executor|Process\(|asyncio|create_task|schema|Store\(|model=|model_config|capture_and_fanout|def .*recovery|_resume_v2_location_transition\(|_resume_cross_module_root\(|queue_live_save\(|cancel_recovery_saves\(' <all ten Python files>
git diff 185f8997 -- '*.py' | rg '^\+' | rg 'Thread|Executor|Process\(|asyncio|create_task|schema|Store\(|model=|model_config|capture_and_fanout|create_completion|register_callsite|legacy|fallback|recovery'
```

Both entrypoints and normal travel use the same continuation. Existing inspector,
receipts, Save manager, scope registry and lifecycle owners retained. Save/exit
siblings reachable through apply_current_transition_action. Startup ownership
precedes completion drain, preserves effects/graph ordering and finishes before
combat/welcome/input. No new worker/runtime/schema/store/model/callsite. Terminal
selection uses the original real managers after scope unwind.

## Remaining gates

Real acceptance, native/browser coverage and independent player-truth review
remain. Baseline issue311 blocks module-final T108 reachability; no review here
waives that gate or authorizes an out-of-scope fix. Full undefined-name scan is
not called clean merely because candidate adds none.

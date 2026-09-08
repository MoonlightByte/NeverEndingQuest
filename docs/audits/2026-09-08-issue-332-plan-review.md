# Issue 332 independent plan review record

Planning artifact, not implementation or acceptance evidence. The frozen plan's
opening PENDING status records its pre-review state; this companion record carries
the later review dispositions without changing the bytes reviewed by each seat.

Frozen plan: 2026-09-08-issue-332-plot-validation-plan.md
SHA256: c41656abfb1f3cacf45baa6740bcc0856160e786a4b8fcd91702d9232004193d
Worktree: /home/loup/neq-worktrees/332-plot-validator-plan
Inspected HEAD and origin/main: 6916507c74d4bbb4795ad9529a69d33c3ce4efe0
Policy initially #193 v3.1 / 2026-09-08T22:46:16Z; rechecked at
2026-09-08T23:06:22Z. New D-323-3 concerns the other level-up work, not #332;
controller read it and reviewers reconfirmed relevant unchanged requirements.

## Method and status

Separate non-author reviewers received the entire plan and resolution ledger,
explicit source worktree, their role/lane/warrant, read-only authority and
evidence requirements. Required roles run in concurrent waves within the active
agent limit. No reviewer received another reviewer's draft. Controller alone
writes. Additional cross-role checks were supplementary, not substitutes for
the distinct required seats below. No production code or model runs occurred.

| Required seat | Agent task | Initial | Confirmation |
| --- | --- | --- | --- |
| Architecture Custodian | 332_arch | PASSED | PASSED |
| Fail-Forward | 332_ff | PASSED | PASSED |
| Acceptance | 322c6_failforward, explicitly reassigned to #332 | PASSED | PASSED |
| Consumer/Compat | 332_independent_compat | PASSED | PASSED |
| Player Experience | 332_independent_px | PASSED | PASSED |
| Leanness | 332_independent_lean | PASSED | PASSED |
| No-Limits | 332_independent_nolimits | PASSED | PASSED |
| Single-Path | 332_independent_singlepath | PASSED | PASSED |

All eight distinct required seats completed a same-SHA clean confirmation.
Review CONVERGED with zero blocking findings. D332-1 owner execution approval
is the remaining gate; this conclusion authorizes no production work.

These are consolidated verdicts, not verbatim raw agent reports. All claims
refer to the frozen plan and inspected source, not future implementation.

## Load-bearing independent checks

- Custodian: party-derived scope main.py:3284; no default module read;
  immutable raw evidence does not authorize progress. Authored future outcomes
  remain distinct from established events (plan lines 110-115). Downstream exact
  target/status/impact and schema/source/write boundaries preserved.
- Fail-Forward: every new read-failure branch CONTINUES into existing review.
  Semantic rejection loops at main.py:10416-10442; currentness/supersession checks
  at 10476-10483 remain. No busy refusal, new timer/retry cap/lock or swallowed
  control exception. Empty plotPoints is evidence, not unavailable.
- Acceptance independently parsed source capture rows 524-527 and distinguished
  the ID-specific false rejection from the separate unsupported rumor claims.
  A payload PASS does not certify mutation. Main/SQ update, negative rejection,
  Load and cross-module currentness retain separate NOT-REACHED verdicts.
- Consumer/Compat: main.py:6883,9370,9775 share _review_dm_candidate -> sole
  validate_ai_response at 10392. The supplied party selects module scope; both
  official modules reuse PP001-PP005 and SQ001-SQ005, so unqualified cross-module
  aggregation would be wrong. Inspected current #322 plots and the July 2025
  Keep save: object roots/list plotPoints, five main and five nested SQ records.
  Frozen plot schema matches origin/main (SHA prefix e9afedbd).
- PX: raw intent remains distinct from the candidate; an authored quest or
  future reward never grants player consent, knowledge, completion or loot.
- Leanness: existing pretty formatter omits SQ IDs; safe_read_json collapses
  failures under broad exception handling. Direct narrowly caught UTF-8/JSON
  reading reuses existing path and serialization without another helper/store.
  Whole-object evidence is approximately 5262/6630 compact JSON characters for
  the inspected official Keep/Thornwood backup plots. These are data sizes, not
  measured live token/performance acceptance.

## FYI and reconciliation

1. Consumer/PX specimen: Thornwood module_plot_BU.json:25-26 (also actual saved
   module_plot.json) has a not-started SQ001 with future reinforcements and an
   Early Warning reward inside plotImpact. The exact proposed instruction's
   future-outcomes warning applies to ALL fields, including plotImpact. Preserve
   this specimen in C2 and transcript review; do not infer that nonempty impact
   means completed event. Disposition: fyi, already covered, no prompt delta.
2. Supplementary Leanness return cited main.py:10396 once; reviewer corrected
   to 10392 by explicit-worktree recheck. Citation error only; no source drift.
   Disposition: fixed-inline in this report.
3. #193 epoch advanced during review. D-323-3 read; no change to this plan's
   authority or requirements. Disposition: fyi; recheck again before execution.
4. No production diff exists. Empty scans are plan-only evidence, never a claim
   of shipped compliance. C2 and later publication gates must scan actual hunks.

## Raw sentinel baseline

Both scans run with explicit planning worktree. Candidate production diff:

```text
$ git diff -- main.py
<empty>
$ git diff -- main.py | rg -n '\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat'
<empty; rg exit 1>
$ git diff -- main.py | rg -n 'legacy|use_new|_v2\b|mode ?==|if .*provider ?==|fallback'
<empty; rg exit 1>
```

Touched main.py No-Limits scan:

```text
3836:                debug(f"Removed duplicate combat system message at index {i}: {content[:60]}...", category="conversation_management")
7136:            "user_input": user_input[:200],  # First 200 chars
7319:                "user_input": user_input[:200],
7462:    main_prompt_start = main_system_prompt_text[:50]  # First 50 characters as identifier
7479:                debug(f"Removing old format system prompt starting with: {msg['content'][:50]}...", category="conversation_management")
7494:            if msg["content"].startswith(main_system_prompt_text[:50]):
8755:            time_display = f"{current_time_str[:5]} ({time_context})"  # Show HH:MM (context)
10627:        print(f"DEBUG: [LocationGraph] First 5 location IDs: {list(location_graph.nodes.keys())[:5]}")
```

Dispositions: 3836/7479/10627 diagnostics; 7136/7319 debug quality-control logs;
7462/7494 prefix comparison keys, full messages still inserted; 8755 HH:MM input
display. None is new payload truncation; this is not approval of unrelated
prefix-identity semantics. Proposed plot JSON has no caps or filters.

Raw single reviewer family:

```text
3232:def validate_ai_response(
6883:            reviewed = _review_dm_candidate(
9370:                review_result = _review_dm_candidate(
9775:    return _review_dm_candidate(
9821:def _review_dm_candidate(
10392:            validation_result = validate_ai_response(
```

The existing nonmembership internal bypass remains unchanged. DM presentation
and T077 mutation are distinct responsibilities, not a second plot-review path.

## Forensic read and unverified limits

Controller re-read actual T067/T065/correction responses in master rows 524-527,
their PP005-bearing request messages, and the ENTIRE compressed T065 system
message actually sent at row525. It requests grounding and correct updatePlot
shape; it does not itself supply authoritative module plot data. Original
malformed-ID diagnosis is not inferred from the final fallback or code alone.

No implementation, current-provider gameplay, fault/cancellation test, native
compatibility run or runtime token/latency acceptance was performed in planning.
No guarantee is made about every future semantic judgment. Live results need
actual consumer payloads, transcripts and disk, with honest unreached boundaries.
Owner decision D332-1 remains pending and blocks implementation.

# #397 implementation and diagnostic report

## Outcome

The narrow repair is implemented and staged in fix/t084-stream-recovery, based on observed origin/main 2940c9f. Commit attempt was refused because native Windows Git has no author name/email configured; no identity was invented or global Git setting changed. The owner was asked which identity to use. It is not committed, merged or pushed. Native gameplay acceptance remains NOT-REACHED; #397 stays open.

The exact tested author prompt replaces example-driven inference and fidelity-overriding caps. T084 OpenAI now uses the registry's Terra/low profile. One private meaning review accepts or rejects each new derivative before any caller receives an approved result. Code checks structure and strict verdict shape, not literal names/possessives. A rejection returns full original history without caching the rejected text. Accepted-cache reads check source equality and structure without another model call. Both prompt identities participate in existing cache keys; source files, five-field cache format, selection, locks, merge/fsync, outbound replacement, T085 and other provider bindings remain unchanged.

The existing format retry now receives its actual latest rejected draft and specific errors privately. No extra retry, cross-turn store, scheduler, provider router or timeout repair was added.

## Review and authority

Owner authorized execution after clean independent review. Nine separate #193 seats and clean confirmation completed before edits. D-397-3 was appended exactly to live #193; read-back epoch 2026-09-14T00:04:48Z. Independent post-code audit and both sentinel scans found no new source defect. A separate simplifier review found no necessary goal-preserving deletion. Post-code checks below were independently reread/rerun.

## Real OpenAI diagnostics

Evidence directory (private, untracked): C:/agent-room-fleet-kit/local-data/issue323/layered-levelup/compression-prompt-tuning-20260913.

All calls requested gpt-5.6-terra, reasoning_effort=low; stream chunks confirmed returned gpt-5.6-terra. Every call completed with stop. Checker SOURCE/CANDIDATE match unchanged real author captures, and complete outputs reconstruct from recorded chunks. Calls ran sequentially.

| Case / JSON artifact | Result | Seconds / first chunk | Input | Output | Total |
|---|---|---:|---:|---:|---:|
| Original combined author: record-16-combined-owner-terra-low.json | Valid JSON; old structure checker rejected alternative EVT layout | 13.156 / 6.007 | 2055 | 1162 | 3217 |
| Faithful check: record-13-checker-faithful-terra-low.json | Accepted | 3.175 / 2.922 | 613 | 14 | 627 |
| Faulty check: record-1-checker-faulty-terra-low.json | Rejected | 13.656 / 11.692 | 1779 | 934 | 2713 |
| Combined check: record-16-checker-combined-terra-low.json | Accepted | 8.069 / 7.966 | 2314 | 532 | 2846 |

New checker total: 6,186 tokens. Including the previously completed single combined-author diagnostic: 9,403 tokens. No additional author tuning runs were made. These are per-call diagnostics, not measured player-turn latency or a general reliability estimate.

All three checker JSON files: requests start at line 5, usage at 28, elapsed at 44, parsed verdict at 47. Companion events.ndjson files: returned model on line 1; terminal usage respectively lines 11, 147 and 11. Exact requests, raw responses and all stream events remain in those artifacts.

The negative check correctly identified invented romance, unsupported early Thane participation, and an added promise. Independent Player-Experience review agreed with all three verdicts. The accepted combined result still omits an apparent sword-rarity descriptor; residual quality belongs to #400, not a claim of perfect preservation.

## Deterministic evidence

Command: python C:/agent-room-fleet-kit/local-data/issue323/layered-levelup/checker-cache-primitives-20260913.py

44 PASSED, independently rerun. Local script and result JSON are beside that command path. Tests compile unchanged production AST definitions for pure parsing and cache I/O; no provider stubs, fabricated model output or gameplay simulation. They cover malformed/contradictory verdicts, actual alternate EVT layouts, exact prompt equality, accepted entry persistence/reload, stale-instance merge, source/runtime invalidation and unchanged selection/reassembly/lock/T085 ASTs.

These I/O tests manually stage an already accepted entry. They do not prove production compress_section makes zero warm calls or never stages a rejected candidate at runtime; source audit establishes those paths as CODE-PROVEN only.

Loaded prompt SHA-256:

- Author: 25683c632e2cff56d76ad575e7d83bfe4af12a1d9d7e0e4bf1d19fefc3f8ca7d
- Checker: 1067ee79e8419f6155a1abafad8f5a27c2838b7078b94943223bcb38feabc1ea

Changed Python files compile. Pyflakes finds zero undefined names; its nonzero exit is limited to inherited unused Path and placeholder-free f-strings. No new diagnostic Python process remains. Native CRLF was retained; use git -c core.whitespace=cr-at-eol diff --check for this already-CRLF-tracked tree. No whitespace-content changes or wholesale EOL conversion to LF were made.

## Remaining work / boundaries

- #397: fresh native product-path acceptance remains NOT-REACHED. No fresh player transcript or authoritative state verdict exists for this patch; downstream DM/validator rendering and private-review isolation are CODE-PROVEN only. Do not close the issue or call the gameplay repaired on this evidence alone.
- #398: provider streaming/liveness and blind waits, next repair after #397 acceptance.
- #400: future author prompt tuning and remaining subtle fidelity issues.
- #402: inherited Local/Custom selected-model cache provenance.
- #403: inherited Windows CRT lock contention exhaustion; not established as player refusal or the 600-second incident cause.
- #404: inherited count-bounded format-correction policy. The feedback fix does not ratify its count limit.
- #276: broader inherited limits; not a substitute for the explicitly scoped findings above.

No owner save, source history, character sheet, spell popup data, main.py, provider transport, WSL configuration or UI was edited. No merge/push/issue closure is authorized by this report.
# Owner supersession: single-pass compression

The owner rejected the private checker and subsequent reference-correction proposal.
The historical plan/results below describe that superseded design, not current code.
Current direction: one Terra/low generation using the consolidated prompt, JSON
extraction, then existing cache and outbound insertion. No semantic/notation
validation, correction call or content-retry loop. Source history and T085 remain
unchanged. Residual dropped names and small fidelity issues remain open in #400.
See 2026-09-13-issue-397-single-pass-report.md for current verification.

# Issue 397: owner-directed single-pass repair

## Current behavior

T084 uses the consolidated historical-memory prompt and registered Terra/low
profile. Each uncached section gets one compression invocation. The JSON envelope
is read and its text enters existing cache/publication handling without semantic
or notation checks, a second reviewer, correction messages, or content retries.
Warm cache reads reuse that text. Source history, section selection, replacement,
cache locking/persistence and the distinct T085 raw-location path are unchanged.
Existing handling of transport errors or unreadable/empty responses remains;
those errors are not reported as successful compression.

The previous checker plan and its reference-correction successor are superseded
by the owner's explicit instruction. Residual omitted names and minor fidelity
errors are unresolved in GitHub issue #400; no extra runtime checker is planned.

## Verification

- Python compilation passed for the compressor, parallel wrapper and registry.
- 25 local checks passed: no semantic/notation validator or correction loop;
  exact author prompt; real captured output cache persistence and warm reuse;
  exact source retention; source/runtime identity invalidation; concurrent-cache
  merge preservation; unchanged selection/replacement, persistence and T085 AST.
- One real OpenAI Terra/low diagnostic on retained record 16 returned JSON:
  15.027 seconds total, 6.251 seconds to first chunk; 2,055 input tokens,
  1,479 output tokens (including 294 reasoning), 3,534 total.
- Cache checks reran using this fresh captured output, without another model call.

Evidence is retained under local-data/issue323/layered-levelup:
single-pass-cache-checks-20260913.py and compression-prompt-tuning-20260913/
record-16-owner-single-pass-final-terra-low.json (with stream/transport artifacts).
These are focused local and provider diagnostics, not a complete live-game test.
No claim of perfect historical fidelity or resolved transport stalls is made.

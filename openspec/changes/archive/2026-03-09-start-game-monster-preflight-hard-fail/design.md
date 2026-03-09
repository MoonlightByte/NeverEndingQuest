## Context

`web/web_interface.py` currently validates module reference integrity during `start_game` and hard-fails immediately on unresolved monster references. This preserves safety, but misses a deterministic one-shot remediation path that already exists in generator tooling.

The desired runtime contract is strict publish gating with bounded recovery:
1) validate,
2) remediate once,
3) revalidate,
4) hard-fail if still unresolved.

## Goals / Non-Goals

**Goals**
- Add deterministic one-attempt remediation before start-game hard fail.
- Preserve strict integrity semantics for unresolved monster references.
- Keep startup host edits small and TABLETOP MODE-marked.
- Provide explicit, actionable operator messages for both remediation and terminal fail states.

**Non-Goals**
- No dynamic runtime degraded mode in this change.
- No change to ingest/watcher strict workflows.
- No relaxation of unresolved-reference publish gate behavior.

## Decisions

1) One-attempt remediation contract (MUST)
- Startup preflight SHALL execute exactly one remediation attempt when `reference_integrity.failed > 0`.
- Additional retries SHALL NOT run in this change.

2) Revalidation is mandatory (MUST)
- Preflight SHALL run a second validator pass after remediation attempt.
- Startup pass/fail decision SHALL be based only on post-remediation reference-integrity result.

3) Strict terminal behavior (MUST)
- If unresolved references remain after remediation, `start_game` SHALL fail and return deterministic actionable system error.
- Startup SHALL NOT continue in degraded mode.

4) Extension-first orchestration (SHOULD)
- Remediation and result shaping SHOULD live in a dedicated helper module under `web/extensions/`.
- `web/web_interface.py` SHOULD remain a thin orchestration hook.

5) Compatibility invariants (MUST)
- Non-failure startup paths remain unchanged.
- Single-player and multiplayer compatibility remains intact.
- Existing validator normalization and reporting semantics remain unchanged.

## Risks / Trade-offs

- [Risk] Startup latency increases on remediation path.
  - Mitigation: one attempt only, no retry loops.
- [Risk] Helper import/runtime errors could block startup incorrectly.
  - Mitigation: explicit fail-closed behavior for unresolved references, fail-open only for non-integrity helper diagnostics.
- [Trade-off] Strict blocking may still interrupt gameplay start.
  - Accepted: this is a release-quality publish gate.

## Migration Plan

1. Add `start_game` preflight helper in `web/extensions/` returning structured outcome.
2. Wire helper into `handle_start_game()` in `web/web_interface.py` before thread launch.
3. Ensure unresolved references trigger one remediation attempt and one revalidation pass.
4. Preserve hard-fail semantics if unresolved references remain.
5. Add regression tests for pass/remediate-pass/remediate-fail paths.

Rollback strategy:
- Remove helper invocation and revert to current direct validation hard-fail branch.
- Keep validator and generator behavior untouched.

## Open Questions

- Resolved in this change: startup remains strict and does not introduce degraded mode.
- Deferred: optional future dynamic validation/retry policies for non-publish local development workflows.

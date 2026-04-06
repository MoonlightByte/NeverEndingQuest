## Context

NEQ already has a partial provider-abstraction layer in `utils/ai_client_factory.py`, but the runtime is not fully migrated to a single router and still contains direct `OpenAI(...)` call sites. That makes a broad provider swap risky and hard to evaluate cleanly.

The Bonsai pilot is intentionally narrower: it asks whether the local Bonsai API can handle the `dm_main` narration path only. This uses the existing provider factory seam without committing the project to a full local-provider architecture.

Constraints:

- The pilot MUST be easy to disable.
- The pilot MUST NOT widen into combat, validation, builders, or other structured paths.
- The pilot MUST keep failure semantics explicit so results are interpretable.
- The operator already knows how to start `bonsai api`; process management is not the thing being evaluated here.

## Goals / Non-Goals

**Goals:**

- Add a bounded `bonsai` chat-provider option through the existing provider factory.
- Route only `dm_main` narration to Bonsai when pilot mode is enabled.
- Fail closed for narration in pilot mode so provider use is unambiguous.
- Preserve existing provider behavior for all non-allowlisted tasks.
- Keep rollout and rollback configuration-driven.

**Non-Goals:**

- universal provider abstraction cleanup
- migration of all direct `OpenAI(...)` call sites
- auto-launching or supervising `bonsai api`
- combat, validation, summary, or builder migration
- new GUI controls beyond what is minimally required for testing

## Decisions

### Decision: Reuse the existing factory seam instead of introducing a new router now

The pilot MUST extend `utils/ai_client_factory.py` rather than introducing a new `llm_router.py` or broader facade.

Why:

- it is the smallest correct surface for a bounded test,
- it minimizes code churn,
- it keeps rollback trivial,
- it avoids coupling the Bonsai evaluation to the broader OpenRouter/router re-architecture.

Alternative considered: implement Bonsai only through a new general router. Rejected because it expands scope beyond the pilot question.

### Decision: Task-level allowlist, starting with `dm_main` only

The pilot MUST use an explicit allowlist that maps only `dm_main` to Bonsai.

Why:

- `dm_main` is the narration path the user wants to evaluate,
- narration is lower risk than validator/combat JSON generation,
- it provides cleaner evidence than a mixed provider rollout.

Alternative considered: route all chat traffic through Bonsai. Rejected because failure or quality regressions would be hard to localize.

### Decision: Fail closed for pilot narration requests

When a Bonsai-routed narration request cannot reach the local API or receives an unhealthy response, runtime MUST return an explicit provider failure and MUST NOT silently fall back.

Why:

- the user wants a pure test run,
- silent fallback would contaminate the evaluation,
- fail-closed behavior makes logs and transcript review meaningful.

Alternative considered: auto-fallback to OpenAI/OpenRouter. Rejected for this pilot because it hides whether Bonsai is really handling narration.

### Decision: Manual Bonsai process ownership

The pilot MUST assume the operator starts `bonsai api` manually.

Why:

- subprocess management adds noise to the experiment,
- a manually started server is simpler to inspect and debug,
- the core question is model usefulness, not process supervision.

Alternative considered: NEQ auto-starts `bonsai api` when missing. Rejected for the pilot because it increases implementation surface and obscures provider-quality results.

### Decision: Explicit Bonsai configuration surface

The pilot SHOULD add dedicated Bonsai config values rather than overloading OpenRouter fields.

Suggested fields:

- `BONSAI_BASE_URL`
- `BONSAI_CHAT_MODEL`
- `BONSAI_API_KEY`
- `BONSAI_PILOT_ENABLED`
- `BONSAI_PILOT_TASKS`
- `BONSAI_FAIL_CLOSED`

Why:

- explicit config makes behavior auditable,
- it prevents accidental provider drift,
- it keeps future router work free to absorb or replace the pilot cleanly.

## Risks / Trade-offs

- [Bonsai prose quality is not strong enough for sustained play] -> Mitigation: keep the pilot bounded to `dm_main` and review real transcripts before widening.
- [Routing logic accidentally touches non-narration tasks] -> Mitigation: use an explicit allowlist plus targeted routing tests.
- [Fail-closed behavior is too disruptive for ordinary play] -> Mitigation: keep fail-closed semantics pilot-only and configuration-gated.
- [Manual server ownership increases operational steps] -> Mitigation: accept this as the correct trade-off for a clean first experiment.
- [Future router work may supersede this slice] -> Mitigation: keep the implementation additive, narrow, and easy to remove or absorb.

## Migration Plan

1. Add pilot configuration fields with safe defaults disabled.
2. Extend provider detection/client creation to support Bonsai API access.
3. Add bounded narration-task routing logic for `dm_main` only.
4. Add fail-closed health/error behavior for Bonsai-routed narration.
5. Add targeted verification for routing isolation and failure semantics.
6. Run manual smoke tests with operator-managed `bonsai api`.

Rollback:

- Disable the pilot config.
- Restore narration routing to the existing provider path.
- No process cleanup contract is needed because NEQ does not own Bonsai server lifecycle in this slice.

## Open Questions

- Should direct DM adjudication turns that share the `dm_main` path be included automatically in the pilot, or should the first slice stay strictly on standard scene narration turns only?
- Should pilot diagnostics surface only in logs, or also in player-facing `[SYSTEM]` output when Bonsai is unreachable?
- After the first evaluation, should summaries be the next candidate task family, or should the experiment stop at narration until broader router work resumes?

## Context

Web Create-with-DM currently spans three layers:
- `web/static/js/tabletop_mode.js` starts the flow through `/api/party/create_player` and immediately reloads the page.
- `web/routes/tabletop_party_routes.py` owns route activation and optional route-based finalization.
- `utils/character_creator.py` owns shared backup, marker, finalization, and recovery helpers.

The recent startup fix established a canonical abort/recovery helper in `utils/character_creator.py` and wired it into `main.py`. The remaining gap is that web route adapters can still return success or error from partial activation/finalization states without calling the shared abort helper.

Constraint layer (MUST):
- Web routes MUST reuse the shared abort helper rather than inventing route-local cleanup logic.
- Repairable invalid-final responses MUST preserve active creation mode.
- Non-retryable route failures MUST fail closed and leave no stale marker trap.
- Host-file edits MUST remain minimal and TABLETOP MODE-safe.

Guidance layer (SHOULD):
- Keep the change backend-focused.
- Avoid frontend/UI expansion unless a backend contract cannot be tested without it.

## Goals / Non-Goals

**Goals:**
- Make `/api/party/create_player` fail closed when activation cannot be completed safely.
- Make `/api/party/finalize_creation` fail closed on terminal errors while preserving retryable validation semantics.
- Align route behavior with the existing shared recovery helper and startup safety net.
- Add deterministic regression coverage for route-level cleanup behavior.

**Non-Goals:**
- Add a new player-facing cancel UI for healthy abandoned creation sessions.
- Redesign the DM interview prompt or schema audit pipeline.
- Replace the startup/main-loop recovery path that already exists.

## Decisions

### Decision: Shared abort helper remains the single cleanup authority
- MUST route all terminal route cleanup through `abort_character_creation_session(...)`.
- Rationale: this keeps marker removal, backup restore, and retry-artifact pruning consistent across startup, main-loop, and route paths.
- Alternative considered: duplicate route-local cleanup in `tabletop_party_routes.py`.
- Rejected because it would create a third lifecycle implementation and likely drift again.

### Decision: `create_player` uses staged activation with fail-closed rollback
- MUST treat marker write success as a prerequisite for returning route success.
- MUST call the abort helper if an exception occurs after backup creation or marker creation but before the route safely completes.
- Rationale: the route is the activation boundary; if it reports success, creation mode must be real and recoverable.
- Alternative considered: keep current best-effort activation and rely on startup recovery.
- Rejected because ordinary route failures should not require a restart to recover.

### Decision: `finalize_creation` distinguishes repairable and terminal failures
- MUST keep creation mode active for `not_candidate` and `needs_retry` results.
- MUST abort the session for terminal failures such as shared-finalizer error, persistence failure, or unexpected finalize status.
- Rationale: only correctable AI output should remain in creation mode; infrastructure/persistence failures should not trap the route in an active session.
- Alternative considered: abort on every non-success finalize result.
- Rejected because it would break the intended iterative correction loop.

### Decision: Keep frontend behavior unchanged for this change
- MUST preserve the existing browser request pattern (`create_player` then page reload).
- SHOULD defer UI cancel affordances to a later change unless backend hardening reveals a hard dependency.
- Rationale: the current bug class is backend lifecycle inconsistency, not missing UI controls.

## Risks / Trade-offs

- Route cleanup could over-fire and close a session that should remain retryable -> Mitigation: only invoke abort helper on terminal 500-class branches and explicit activation failures, not on `needs_retry` / `not_candidate`.
- Marker rollback could hide a deeper persistence bug -> Mitigation: keep structured logs with explicit reason strings for every abort path.
- Existing route tests may only prove source wiring, not runtime cleanup -> Mitigation: add focused runtime tests using temporary history/marker files or mocked helpers.
- Route activation ordering may still depend on queue behavior -> Mitigation: treat queue failure as terminal and abort immediately.

## Migration Plan

1. Update route imports and integrate shared abort helper into `create_player` and `finalize_creation`.
2. Add or extend source-contract tests to lock the new helper usage and retry/terminal branch behavior.
3. Add focused runtime tests for activation rollback and finalize failure cleanup.
4. Run compile and targeted test suite.
5. If a regression appears, rollback by removing only the new route helper calls; startup/main-loop recovery remains intact as fallback.

## Open Questions

- None for the backend hardening slice. Explicit user-facing cancel UX remains intentionally deferred.

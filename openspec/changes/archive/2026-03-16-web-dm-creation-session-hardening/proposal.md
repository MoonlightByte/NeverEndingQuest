## Why

The startup/main-loop recovery fix closes poisoned Create-with-DM sessions after terminal failure, but the web route adapters still have split lifecycle behavior that can orphan creation state on partial failures. We need route-level fail-closed parity so ordinary web errors do not rely on a later restart to recover.

## What Changes

- Add fail-closed activation semantics to `/api/party/create_player` so marker creation, prompt queueing, and success responses stay atomic from the route's perspective.
- Add terminal-error cleanup semantics to `/api/party/finalize_creation` so non-retryable failures abort the creation session and restore prior narrative state.
- Preserve existing repairable retry behavior for incomplete or invalid final JSON so creation mode remains active only for correctable cases.
- Add focused regression coverage for route-level cleanup and source-contract parity with the shared character-creation recovery helper.
- SHOULD keep the implementation backend-focused and avoid expanding UI scope unless needed to satisfy the route contract.

## Capabilities

### New Capabilities
- `tt-web-creation-session-recovery`: deterministic fail-closed lifecycle for web Create-with-DM session activation and terminal route failures.

### Modified Capabilities
- None.

## Impact

- Affected code: `web/routes/tabletop_party_routes.py`, `utils/character_creator.py`, and route/contract regression tests under `scripts/`.
- Affected APIs: `/api/party/create_player` and `/api/party/finalize_creation`.
- Systems: web Create-with-DM flow, conversation backup/restore handling, creation marker lifecycle, startup compatibility with already-broken sessions.
- Risk: low-to-medium; touches user-facing creation flow and must preserve repairable retry behavior while cleaning terminal failures.
- Fallback: if any new route cleanup path degrades, startup poisoned-session recovery remains as the last-resort safety net.

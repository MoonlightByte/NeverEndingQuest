## 1. Route Activation Hardening

- [x] 1.1 Harden `/api/party/create_player` in `web/routes/tabletop_party_routes.py` so marker persistence is checked explicitly and any post-marker activation failure aborts the creation session via the shared helper; verify with `python3 -m py_compile web/routes/tabletop_party_routes.py`.
- [x] 1.2 Preserve current repairable retry behavior for `/api/party/finalize_creation`, but abort the creation session on terminal finalizer, persistence, or unexpected-status failures; verify with `python3 -m py_compile web/routes/tabletop_party_routes.py`.

## 2. Regression Coverage

- [x] 2.1 Extend route source-contract coverage in `scripts/test_party_finalize_creation_adapter.py` (and add a paired create-player contract test if needed) so helper usage and retry-vs-terminal semantics are locked; verify by running the touched source-contract scripts.
- [x] 2.2 Add focused runtime regression tests for route-level cleanup and activation rollback using temporary conversation-history/marker files or mocked helpers; verify by running the new runtime test script.

## 3. Verification

- [x] 3.1 Run targeted validation for the hardening slice: `python3 -m py_compile web/routes/tabletop_party_routes.py utils/character_creator.py` plus all touched route/creation test scripts.
- [x] 3.2 SHOULD perform one manual smoke pass of web Create-with-DM start -> invalid final -> terminal failure simulation to confirm no stale `creation_mode_active.json` remains after failure.

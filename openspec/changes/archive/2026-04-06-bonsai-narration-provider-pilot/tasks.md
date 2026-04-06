## 1. Config and Contract Scaffolding

- [ ] 1.1 Add Bonsai pilot configuration fields to `model_config.py` and `config_template.py` with disabled-by-default semantics.
- [ ] 1.2 Add targeted source-contract or routing tests that lock the intended pilot scope to `dm_main` only.
- [ ] 1.3 Add explicit documentation or comments that the pilot expects an already-running `bonsai api` server and does not auto-launch it.

## 2. Provider Factory Routing

- [ ] 2.1 Extend `utils/ai_client_factory.py` so a Bonsai-configured chat client can be created through the OpenAI-compatible local API.
- [ ] 2.2 Add bounded pilot routing logic that selects Bonsai only for allowlisted narration tasks.
- [ ] 2.3 Keep all non-allowlisted tasks on the existing provider path without changing their current fallback behavior.

## 3. Fail-Closed Narration Behavior

- [ ] 3.1 Add a bounded health or connectivity check for Bonsai-routed narration requests.
- [ ] 3.2 Ensure Bonsai-routed narration failures surface explicit diagnostics and do not silently fall back during pilot mode.
- [ ] 3.3 Verify NEQ does not attempt to spawn or supervise `bonsai api` as part of the pilot.

## 4. Verification

- [ ] 4.1 Run targeted tests proving `dm_main` routes to Bonsai only when the pilot is enabled.
- [ ] 4.2 Run targeted tests proving validation, combat, and other non-allowlisted tasks remain on the existing provider path.
- [ ] 4.3 Run a fail-closed smoke case with Bonsai unavailable and verify explicit narration failure behavior.
- [ ] 4.4 Run `python3 -m py_compile` on all touched Python files.
- [ ] 4.5 Run `openspec validate bonsai-narration-provider-pilot`.

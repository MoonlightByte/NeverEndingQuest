## 1. Router and Profile Scaffolding

- [ ] 1.1 Add `MODEL_PROFILES`, `DEFAULT_PROFILE`, and capability classification constants in `model_config.py` with safe defaults for OpenAI-first operation (verify: `python -m py_compile model_config.py`).
- [ ] 1.2 Add profile validation helper(s) and normalized profile resolution API in `utils/ai_client_factory.py` or `utils/llm_router.py` per design boundary (verify: unit-level sanity checks for missing/partial profiles).
- [ ] 1.3 Normalize provider extra parameter shape handling to SDK-compatible kwargs (especially `extra_body`) to prevent unsupported keyword errors (verify: targeted test covering thinking params path).

## 2. Facade Core Implementation

- [ ] 2.1 Create `utils/llm_router.py` with `llm.call(...)` facade and clear separation of responsibilities vs factory/client creation (verify: `python -m py_compile utils/llm_router.py`).
- [ ] 2.2 Implement task-driven model/profile selection in router with complex/simple path selection and fallback to base model when profile fields are absent (verify: tests for complex task, simple task, and missing profile fallback).
- [ ] 2.3 Implement response normalization so callsites receive backward-compatible content shape for phase 1 adoption (verify: smoke check against one existing narration caller contract).

## 3. Error Policy and Fallback Behavior

- [ ] 3.1 Implement router error classification map for retryable transient failures vs hard-stop failures (verify: tests for timeout/429/503 and invalid-auth/quota terminal paths).
- [ ] 3.2 Integrate bounded retry and deterministic provider fallback using existing factory hooks (`handle_provider_error`) without duplicating provider logic (verify: simulated retryable failure triggers fallback once and returns expected outcome).
- [ ] 3.3 Add categorized warning/error logging for profile failures and terminal provider errors with ASCII-safe log text (verify: grep/check no Unicode markers in new Python logging messages).

## 4. Observability and Thread Safety

- [ ] 4.1 Add router usage/fallback/error counters behind lock-protected shared state in `utils/llm_router.py` (verify: concurrent update test with consistent totals).
- [ ] 4.2 Expose `get_usage_stats()` (and reset helper for tests if needed) with stable key names for migration diagnostics (verify: stats schema test and manual call in REPL).
- [ ] 4.3 Add optional cost/token estimate capture when provider usage metadata exists, with no failure when metadata is absent (verify: one test with usage payload and one without).

## 5. Pilot Integration and Verification

- [ ] 5.1 Migrate a minimal pilot set of low-risk chat callsites to `llm.call(...)` while preserving existing behavior (target files documented in change notes; verify: `python -m py_compile` on modified modules).
- [ ] 5.2 Run focused smoke checks for startup, narration response, combat validation path, and summary generation path in OpenAI default mode (verify: command outputs/log traces show no regression).
- [ ] 5.3 Run fallback-path smoke check in OpenRouter mode by simulating retryable failure and confirming provider-switch handling/logging (verify: fallback counter increments and operation completes or fails clearly).

## 6. Documentation and Handoff

- [ ] 6.1 Update architecture documentation to describe facade/factory/config boundaries and phase-2 migration handoff (`plans/version-2/openrouter_llm_router_architecture.md` and/or docs file) (verify: docs reference current file paths and interfaces).
- [ ] 6.2 Record rollout and rollback procedure in implementation notes for operators (verify: includes enable path, disable path, and failure triage steps).

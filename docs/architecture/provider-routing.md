# Provider Routing

Purpose: bind each registered T-ID to one provider-specific model profile, execute the selected request through one normalized transport boundary, and keep capture evidence observational.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

Branch delta: voices `8f51bef3ee39e8f86b9bff635816c2dd6a520082` adds T105/T107/T108/T112/T113 registry profiles and task-owned advisory child scopes; it does not change the router, capture writer, API logger, or provider clients described here.

Startup delta verified 2026-09-05 against the `fix/issue-114-startup-repair` working candidate based on `3f521f70429cf9bef4e0a5688d11c4fce44f7596`: T092 author/reviewer and T093 location work use the existing required live path. Unchanged routing anchors retain the earlier pin; live #193 remains doctrine authority.

## Authority table

| Datum | Source of truth | Explicit non-authority |
|---|---|---|
| Current provider | `model_config.MODEL_PROVIDER`, initialized from ignored `user_settings.json` | Stale imported globals and old `USE_*` toggles |
| Per-T-ID profile | Immutable `model_registry.CALLSITE_BINDINGS` | Legacy model argument and capture configuration |
| Attempt profile | Deep copy from `resolve_callsite_config(task_id, provider, attempt)` | Background variant overrides |
| Effective production request | `capture_and_fanout` provider snapshot plus registry-owned replacements and callsite overlays | Telemetry/capture output |
| Live transport identity | Active scope operation ID plus physical child generation | Capture invocation ID |
| Provider adapter | `api_client.create_completion` | Retry policy or model selection |
| Successful response | Normalized content, usage, provider, T-ID, reported model, and response ID | Pre-call model constant |
| Evidence | API/capture/usage logs | Gameplay or persisted-state authority |

## Flow

1. Import-time settings load reads installation-root `user_settings.json`. An explicit saved provider wins; otherwise OpenAI is selected.
2. `set_provider` updates `model_config` and already-imported compatibility globals. Supported providers are `openai`, `gemini`, `legacy`, and `lmstudio`.
3. Registry construction rejects duplicate T-IDs. Validation checks the exact inventory, nonempty provider ladders, named profiles, models, and supported reasoning effort.
4. A callsite builds its messages and callsite-owned schema, format, temperature, and other overlays, then calls `capture_and_fanout(T-ID, api_client.create_completion, ...)`.
5. The boundary snapshots the provider once so an in-flight UI setting change cannot redirect the call.
6. It resolves the registered ladder at `min(attempt,last)`, replaces only registry-owned model/reasoning/thinking/token-profile fields, and deep-copies the effective request.
7. For the standard adapter it injects the provider snapshot, task ID, and usage invocation UUID. Raw SDK-compatible functions do not receive private metadata.
8. A live-selected T-ID freezes request bytes and starts one provider child per generation. Polling checks supersession, fully terminates and reaps a stale child, and accepts only an envelope matching operation ID and generation.
9. Outside live transport, primary retry makes up to three physical calls only for typed empty response. Other provider and transport errors propagate immediately.
10. `create_completion` enforces API compatibility and routes OpenAI, Legacy, and LM Studio through the OpenAI-compatible client; Gemini uses `google.genai` and its conversion layer.
11. Unexpected provider exceptions become correlated `ProviderCallError`; empty or non-text output is rejected; success is normalized to one OpenAI-shaped response.
12. Usage recording is independent of capture and failure-isolated. If capture is disabled, the primary response returns immediately.
13. When both the outer capture gate and JSON `capture_enabled` are true, one successful-primary record is written and enabled nonduplicate OpenAI/Gemini variants may enter the eight-worker pool. Live-selected tasks receive no background variants; LM Studio returns before fanout.
14. Capture errors never affect gameplay, and process exit waits for background capture workers.
15. Capture task overrides select variants only. The sole production override is the registered attempt ladder, except the constrained OpenAI evaluation-primary mode available only while capture is enabled.
16. Callsite schema/format/temperature overlays survive registry resolution. The adapter removes unsupported combinations per provider, including `top_p` and incompatible temperature/effort/schema forms.
17. Local/Custom may replace only the LM Studio model from persisted settings and omits unsupported `json_object` while preserving explicit JSON schema.
18. Required live tasks structurally reissue after a fully reaped unavailable generation. Advisory tasks terminate for that beat. The live policy, not capture, owns this distinction.
19. Startup supplies a private reactive message-repair callback when a provider rejects request ordering. The live transport invokes it only after the correlated failed child is reaped, then freezes the repaired messages for the next generation. It does not fabricate a response or change provider selection.
20. Capture removes that callback before serialization/API dispatch and records the actual repaired message sequence. Independent startup review uses the existing T092 binding; no parallel startup router or model-specific gameplay branch is introduced.

## State and atomicity

- In-memory authority includes the immutable registry, provider/config globals, active live scope, child generation, capture config cache, executor, and usage-deduplication cache.
- Installation settings use ignored `user_settings.json`; credentials prefer the OS secret store and fall back to an owner-only ignored file when required.
- Settings writes use Windows binary mode, a temporary file, and `os.replace`, with best-effort owner-only permissions.
- Live provider children use the current Python executable and binary pipes. Streams and processes are explicitly closed or terminated before a generation is replaced.
- Multi-model capture uses `NEQ_MODEL_CAPTURE_DIR` and `NEQ_MODEL_CAPTURE_CONFIG`; enablement also requires `NEQ_MULTI_MODEL_CAPTURE` or the configured flag and literal JSON `capture_enabled`.
- Capture records use an in-process lock, native file locking, fsync, and same-filesystem replace; corrupt files are quarantined.
- API master JSONL serializes before an in-process append lock and does not claim cross-process locking.
- At this pin, per-T-ID primary capture lacks actual `response.model`, provider response ID, and usage invocation ID. The API master has actual model but lacks response ID/shared correlation, so neither store alone proves exact request-to-response identity.
- Source-revision capture hashes runtime Python and prompt/schema inputs, but its Git subprocess probes have no bound; issue #250 tracks that evidence-path liveness gap.

## Load-bearing seams

1. `model_registry.py:14-39` - supported providers and eligible model catalog.
2. `model_registry.py:75-113` and `model_registry.py:573-594` - binding schema and immutable inventory.
3. `model_registry.py:268-310` and `model_registry.py:413-429` - representative validator and main-DM bindings.
4. `model_registry.py:495-520` - T096/T097 profiles and attempt ladders.
5. `model_config.py:1018-1124` - capture defaults, provider defaults, and switching.
6. `model_config.py:1147-1388` - persisted settings and credentials.
7. `model_config.py:1391-1521` - registry validation, resolution, and derived variants.
8. `utils/capture/multi_model_capture.py:323-376` - profile replacement and empty-only retry.
9. `utils/capture/multi_model_capture.py:379-498` - provider snapshot and primary execution.
10. `utils/capture/multi_model_capture.py:500-620` - failure-isolated capture and variants.
11. `core/ai/api_client.py:181-263` - response rejection and actual model/ID normalization.
12. `core/ai/api_client.py:280-367` - provider-neutral router and error normalization.
13. `core/ai/api_client.py:370-552` - provider constraints and Gemini translation.
14. `utils/capture/live_provider_call.py:735` and `utils/capture/multi_model_capture.py:380` - live children, correlation, required reissue, reactive request repair, and capture bookkeeping (startup candidate).
15. `utils/capture/file_writer.py:36-181` and `utils/api_logger.py:42-123` - capture and API evidence stores.

## Invariants

- See #193 Part 1 for B1/B2, AP-5, evidence, lineage, and governance.
- See #193 Part 2 pages 3, 4, 8, 10, 11, 12, and 13 for build/combat callers, compression, threading, provider binding, compatibility, and real acceptance.
- See #193 Part 5 for structural liveness, Single Path, and No-Limits rulings.
- This document describes the pinned implementation. If it conflicts with current #193, #193 controls.

## Open items

- Routing and liveness: #186, #204, #239, #240, and #250.
- Player-visible provider failures: #170, #179, #232, and #233.
- Provider/schema/platform debt: #148 and #166.

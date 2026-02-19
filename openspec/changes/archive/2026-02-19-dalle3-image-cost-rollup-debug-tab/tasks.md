## 1. Pricing and tracker foundation

- [x] 1.1 Add additive DALL-E 3 pricing config in `model_config.py` for supported `size` and `quality` combinations with safe defaults.
- [x] 1.2 Add cost-only image event tracking helper in `utils/llm_usage_tracker.py` that updates session/week USD and NZD while preserving token counters.
- [x] 1.3 Re-export new helper in `utils/openai_usage_tracker.py` to keep compatibility import path stable.
- [x] 1.4 Verify compile: `python3 -m py_compile model_config.py utils/llm_usage_tracker.py utils/openai_usage_tracker.py`.

## 2. Image callsite instrumentation

- [x] 2.1 Instrument `core/toolkit/portrait_service.py` successful generation path with fail-open image-cost tracking.
- [x] 2.2 Instrument `core/toolkit/npc_generator.py` and `core/toolkit/monster_generator.py` successful generation paths with fail-open image-cost tracking.
- [x] 2.3 Instrument `web/web_interface.py` `generate_image` socket flow successful generation path with fail-open image-cost tracking and retry-safe single-count behavior.
- [x] 2.4 Verify compile: `python3 -m py_compile core/toolkit/portrait_service.py core/toolkit/npc_generator.py core/toolkit/monster_generator.py web/web_interface.py`.

## 3. Regression coverage

- [x] 3.1 Extend `scripts/test_usage_rollups_debug_tab.py` with cost-only image event tests.
- [x] 3.2 Add assertions that image-cost events do not increase token counters.
- [x] 3.3 Add mixed-session assertions (chat token events + image cost-only events) for rollup consistency.
- [x] 3.4 Run tests: `python3 scripts/test_usage_rollups_debug_tab.py`.

## 4. Final verification

- [x] 4.1 Run compile checks across all modified files.
- [x] 4.2 Run `openspec validate dalle3-image-cost-rollup-debug-tab`.
- [x] 4.3 Manual smoke: trigger portrait create and verify Debug tab session/week cost increases while token totals remain stable for that event.

SHOULD guidance (non-blocking): keep image context metadata concise (`endpoint`, `purpose`, `model`, `size`, `quality`, `n`) so telemetry remains readable.

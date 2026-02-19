Use this file as the builder execution scaffold for `tasks.md`.

---

## Execution Contract

- MUST execute in order: Prompt 1 -> Prompt 4.
- MUST keep existing `token_update` fields and behavior unchanged.
- MUST keep token counters unchanged for image-cost events.
- MUST keep tracking fail-open (generation success cannot be blocked by telemetry failure).
- MUST keep Python-visible text ASCII-only.
- SHOULD keep implementation additive and merge-safe.

---

## Prompt 1 - Pricing + Tracker Foundation

Implement tasks 1.x.

Scope:
- `model_config.py`
- `utils/llm_usage_tracker.py`
- `utils/openai_usage_tracker.py`

Requirements:
- Add DALL-E 3 per-image pricing config entries.
- Add cost-only image event tracking helper that updates session/week USD and NZD.
- Keep token counters untouched for this path.
- Preserve compatibility shim imports in `utils/openai_usage_tracker.py`.

Verify before moving on:
- `python3 -m py_compile model_config.py utils/llm_usage_tracker.py utils/openai_usage_tracker.py`

---

## Prompt 2 - Callsite Instrumentation

Implement tasks 2.x.

Scope:
- `core/toolkit/portrait_service.py`
- `core/toolkit/npc_generator.py`
- `core/toolkit/monster_generator.py`
- `web/web_interface.py`

Requirements:
- Add fail-open image-cost tracking after successful image generation calls.
- Include concise context metadata (endpoint/purpose/model/size/quality/n).
- Ensure retry flows count one final success event only.

Verify before moving on:
- `python3 -m py_compile core/toolkit/portrait_service.py core/toolkit/npc_generator.py core/toolkit/monster_generator.py web/web_interface.py`

---

## Prompt 3 - Regression Tests

Implement tasks 3.x.

Scope:
- `scripts/test_usage_rollups_debug_tab.py`

Requirements:
- Add image cost-only event tests.
- Assert cost rollups increase.
- Assert token counters remain unchanged for image events.
- Assert mixed-session rollups remain coherent.

Verify before moving on:
- `python3 scripts/test_usage_rollups_debug_tab.py`

---

## Prompt 4 - Final Validation

Implement tasks 4.x.

Scope:
- all changed files

Required final commands:
- `python3 -m py_compile model_config.py utils/llm_usage_tracker.py utils/openai_usage_tracker.py core/toolkit/portrait_service.py core/toolkit/npc_generator.py core/toolkit/monster_generator.py web/web_interface.py`
- `python3 scripts/test_usage_rollups_debug_tab.py`
- `openspec validate dalle3-image-cost-rollup-debug-tab`

Manual smoke checklist:
1. Trigger portrait create from Character Sheet.
2. Confirm Debug tab session/week USD/NZD values increase.
3. Confirm token totals do not jump from that image-cost event alone.

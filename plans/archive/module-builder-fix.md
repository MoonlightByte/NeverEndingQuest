# Module Builder Fix & Generator Client Migration
**Status:** COMPLETED
**Priority:** High (Blocks Module Builder)
**Date:** 2026-03-31

## Objective
Fix the `openai.BadRequestError: 400 - We could not parse the JSON body of your request` error occurring during module generation (specifically in `plot_generator.py`). Complete the Phase 1B OpenRouter migration for the `core/generators/` directory to ensure proper multi-provider routing, context payload optimization, and fallback resiliency.

## Root Cause
1. **Legacy Client Instantiation:** Generators are still using direct `OpenAI(api_key=OPENAI_API_KEY)` calls. When routed through proxies or OpenRouter without proper headers, large payloads or specific `response_format` configurations can be rejected with 400 Bad Request parsing errors.
2. **Context Bloat:** `plot_generator.py` injects `context.to_dict()` directly into the prompt. For heavily populated modules, this stringifies massive nested dictionaries (areas, locations, NPCs), producing 70KB+ payloads that increase the risk of HTTP body truncation or model parsing failures.
3. **Lack of Resiliency:** The generators lack the `try/except` fallback loop utilizing `utils.ai_client_factory.handle_provider_error()`, causing transient network or proxy drops to crash the entire build process.

## Implementation Plan

### Phase 1: Context Payload Optimization in `plot_generator.py`
- Modify `generate_plot_structure` to accept a slimmed-down context.
- Instead of dumping the entire `module_context`, extract only narrative-critical information:
  - Module name & objective
  - Area names, descriptions, and danger levels
  - Location names and types (excluding full map arrays/coordinates)
  - NPC names, roles, and factions (excluding full stat blocks)
- This will reduce the payload size by 80-90% while retaining all necessary creative context.

### Phase 2: Factory Client Migration for `plot_generator.py`
- Replace `from openai import OpenAI` with `from utils.ai_client_factory import create_chat_client, get_model_config, handle_provider_error`.
- Replace module-level `client = OpenAI(...)` with local/instance `client = create_chat_client()`.
- Update `client.chat.completions.create` calls to use `get_model_config()` for model selection and `**config.get("extra_body", {})`.
- Add retry loops with `use_fallback=True` on provider errors.

### Phase 3: Sibling Generator Audit & Migration
Audit all files in `core/generators/` for legacy `OpenAI` client usage and migrate them to the factory pattern:
- `module_builder.py` (specifically `unify_plots`)
- `location_generator.py`
- `npc_generator.py`
- `monster_generator.py`
- `combat_builder.py` / `encounter_builder.py`

### Phase 4: Verification
- Run syntax checks on all modified files.
- Test JSON serialization of the new slim context.
- Verify module building doesn't crash on prompt generation.

## Execution
Implementation will proceed immediately following this plan.
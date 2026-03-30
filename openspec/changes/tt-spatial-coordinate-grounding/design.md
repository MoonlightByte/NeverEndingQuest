## Architecture Boundaries
- **Ingest Pipeline:** `core/importers/homebrewery_importer.py` will receive a new helper function `_resolve_spatial_layout()` to act as the LLM Cartographer pass before `_emit_map_file()`.
- **Legacy Backfill:** A new developer script `scripts/remediate_module_coordinates.py` will read existing area files, preserve their connections, generate new coordinates via LLM, and safely write them back.
- **Validation Gate:** `core/validation/validate_module_files.py` will add a "Spatial Coherence" check. Connected rooms should ideally be within a mathematical distance of 2 (Manhattan distance). 

## Factory Responsibilities
- MUST use `utils.ai_client_factory.create_chat_client(use_fallback=True)` for the LLM cartography calls to ensure OpenRouter/OpenAI fallback resiliency during ingest and remediation.
- MUST use the `DM_MAIN_MODEL` or a designated JSON-capable model configuration for spatial parsing.

## Trade-offs and Heuristics
- SHOULD instruct the LLM to use a central starting coordinate like `X10Y10` to avoid negative numbers which may complicate `map_` JSON array layout rendering.
- SHOULD treat the LLM coordinates as directional hints (N/S/E/W) rather than perfect Euclidean space. If a room connects two distant areas, coordinate gaps are acceptable.
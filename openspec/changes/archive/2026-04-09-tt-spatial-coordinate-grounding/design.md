## Architecture Boundaries
- **Ingest Pipeline:** `core/importers/homebrewery_importer.py` should perform a semantic spatial resolution pass before emitting area and map artifacts.
- **Toolkit Builder:** Current builder-side spatial preparation belongs in the active generation surfaces, primarily `core/generators/area_generator.py` and `core/generators/location_generator.py`.
- **Legacy Backfill:** `scripts/remediate_module_coordinates.py` should backfill the spatial contract for existing modules while preserving authored connectivity.
- **Validation Gate:** `core/validation/validate_module_files.py` should distinguish strict new-output validation from warn-first legacy validation.

## Spatial Contract Boundaries

This change now covers four authored outputs:
- `coordinates`
- `tactical_grid`
- `aliases`
- cardinal `directions`

Contract notes:
- `coordinates` remain `X#Y#` strings.
- `tactical_grid` is a 9-element environmental stage only.
- `aliases` are prose-derived alternate location references.
- `directions` are limited to `north`, `south`, `east`, and `west` for this prep phase.
- Vertical travel metadata is explicitly deferred.

## Runtime Boundary

This change is a data-preparation slice only.

It does not implement:
- map UI rendering
- `request_map_data` socket payloads
- worldview graph persistence
- new runtime movement semantics

## Factory Responsibilities
- MUST use `utils.ai_client_factory.create_chat_client(use_fallback=True)` for any LLM-backed spatial inference.
- MUST use a JSON-capable model path for spatial parsing and strict structured extraction.

## Trade-offs and Heuristics
- SHOULD use a central starting coordinate like `X10Y10` to avoid negative boundaries during layout generation.
- SHOULD treat coordinates as semantic directional grounding, not exact Euclidean simulation.
- SHOULD require builder and ingest outputs to converge on the same artifact shape so later v2 consumers do not need separate loaders.
- SHOULD fail strict new-output readiness when required spatial fields are missing, while keeping legacy validation warn-first until remediation is complete.

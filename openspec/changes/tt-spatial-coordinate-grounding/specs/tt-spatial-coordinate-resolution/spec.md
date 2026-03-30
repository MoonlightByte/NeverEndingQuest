## Purpose
To ensure that all imported and legacy modules possess semantically grounded `X#Y#` coordinates, allowing the "DM Local Grid" to accurately represent the physical space relative to narrative descriptions.

## Requirements

- `homebrewery_importer.py` MUST invoke an LLM spatial cartographer before emitting map and area files to resolve connected rooms to 2D coordinates.
- The LLM cartographer MUST assign coordinates such that rooms described as adjacent or directional (e.g., North, South) are assigned relative coordinates (`Y-1`, `Y+1`, `X+1`, `X-1`).
- `scripts/remediate_module_coordinates.py` MUST be created to perform targeted backfill for legacy modules without altering their `connectivity` arrays.
- `scripts/remediate_module_coordinates.py` MUST support `--dry-run` and `--apply` flags.
- `core/validation/validate_module_files.py` MUST include a "Spatial Coherence" check that warns or fails if connected rooms are mathematically distant without justification.

## Implementation Guidance

- SHOULD use `X10Y10` as a default starting coordinate to prevent negative boundaries.
- SHOULD limit the LLM's response to strict JSON mapping `room_id -> coordinate` to prevent hallucinatory parsing.
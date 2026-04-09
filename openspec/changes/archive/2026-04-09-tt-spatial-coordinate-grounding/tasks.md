## 1. Spatial Resolution Helper
- [x] 1.1 Add or expand a shared spatial inference helper for semantic room placement from descriptions and connectivity.
- [x] 1.2 Ensure the helper can support builder, ingest, and remediation callers without duplicating prompt logic.
- [x] 1.3 Add focused tests for structured output parsing and malformed-response handling.

## 2. Toolkit Builder Parity
- [x] 2.1 Update the active builder spatial generation surface in `core/generators/area_generator.py` to emit semantically grounded coordinates and cardinal directions.
- [x] 2.2 Update `core/generators/location_generator.py` to emit per-location `tactical_grid` and `aliases`.
- [x] 2.3 Add regression coverage proving builder outputs include the new spatial contract fields.

## 3. Homebrew Ingest Parity
- [x] 3.1 Update `core/importers/homebrewery_importer.py` to resolve semantic coordinates before emitting map and area artifacts.
- [x] 3.2 Emit `tactical_grid` and `aliases` during ingest artifact generation.
- [x] 3.3 Emit explicit cardinal `directions` in `map_<AREA>.json` based on the resolved layout.
- [x] 3.4 Add regression coverage proving ingest outputs match the builder contract shape.

## 4. Schema and Validator Updates
- [x] 4.1 Update `schemas/loca_schema.json`, `schemas/locationfile_schema.json`, and `schemas/map_schema.json` for the expanded spatial contract.
- [x] 4.2 Update `core/validation/validate_module_files.py` to validate spatial coherence and field presence.
- [x] 4.3 Make validator behavior strict for new build/ingest outputs and warn-first for legacy modules.

## 5. Legacy Remediation Tooling
- [x] 5.1 Expand `scripts/remediate_module_coordinates.py` to backfill `coordinates`, `tactical_grid`, `aliases`, `directions`, and layout parity as needed.
- [x] 5.2 Support `--dry-run` and `--apply` modes.
- [x] 5.3 Add regression coverage proving authored `connectivity` and unrelated content remain untouched.

## 6. Verification
- [x] 6.1 Verify newly ingested gameplay-test modules pass the spatial validator without warnings.
- [x] 6.2 Verify newly built toolkit modules emit the same spatial contract as ingested modules.
- [x] 6.3 Verify legacy modules still fail open at runtime while remaining warn-first until remediated.

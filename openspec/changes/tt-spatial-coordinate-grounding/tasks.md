## 1. LLM Cartography Helper
- [ ] 1.1 Add `utils/spatial_cartographer.py` with an LLM spatial inference helper that takes room metadata (descriptions/connections) and outputs a mapping of `room_id -> coordinate` starting at `X10Y10`.
- [ ] 1.2 Write unit tests for `spatial_cartographer.py` to ensure it parses valid JSON grids and handles fallback gracefully.

## 2. Ingest Pipeline Integration
- [ ] 2.1 Update `core/importers/homebrewery_importer.py` to call the cartography helper before `_emit_map_file()`.
- [ ] 2.2 Verify `map_<AREA>.json` and `areas/<AREA>.json` correctly emit the LLM-derived `coordinates` instead of `X#Y0`.

## 3. Legacy Remediation Tooling
- [ ] 3.1 Create `scripts/remediate_module_coordinates.py` that reads an existing area file, preserves connections, invokes the cartography helper, and rebuilds the `coordinates` and `layout` safely.
- [ ] 3.2 Add `--dry-run` and `--apply` flags to the script.
- [ ] 3.3 Add regression coverage for the remediation script to ensure `connectivity` remains untouched.

## 4. Readiness Validator Update
- [ ] 4.1 Update `core/validation/validate_module_files.py` to include a "Spatial Coherence" check.
- [ ] 4.2 Have the validator output warnings if connected rooms are mathematically distant (e.g., > 2 steps).
## 1. Authored Adjacency Extraction

- [x] 1.1 Add a deterministic authored-adjacency extraction path for imported room records, using explicit room-reference and directional cues before sequential fallback.
- [x] 1.2 Keep extraction bounded and fail-open so weak or ambiguous prose falls back to the current safe ingest connectivity scaffold.
- [x] 1.3 Add focused helper tests for explicit adjacency, non-linear adjacency, and fallback-to-sequential behavior.

## 2. Ingest Integration

- [x] 2.1 Update `core/importers/homebrewery_importer.py` to build room connectivity from authored adjacency extraction before calling `resolve_semantic_spatial_plan(...)`.
- [x] 2.2 Ensure emitted map `connections`, `directions`, and `layout` remain aligned to the extracted graph and shared planner output.
- [x] 2.3 Add ingest regression coverage proving non-linear source structures no longer collapse to previous/next ordering when stronger authored adjacency exists.

## 3. Strict Spatial Coherence Validation

- [x] 3.1 Extend `core/validation/validate_module_files.py` to fail strict spatial-contract outputs when directly connected rooms are not cardinally adjacent.
- [x] 3.2 Extend validation to fail strict outputs when `directions` entries contradict coordinate deltas.
- [x] 3.3 Preserve warnings-only behavior for legacy modules and add regressions proving strict failures do not spill into legacy validation mode.

## 4. Verification

- [x] 4.1 Run targeted spatial regression suites covering helper, importer, and validator behavior.
- [x] 4.2 Run module validation against at least one real gameplay-test module to confirm no unintended strict regressions.
- [x] 4.3 Review `plans/module-maps.md` archive gate and confirm the remaining open items for that plan are satisfied by this change.

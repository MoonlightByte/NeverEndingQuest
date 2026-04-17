## 1. Normalization Prompt and Service

- [x] 1.1 Add a dedicated Homebrew normalization prompt that instructs the model to produce a source-faithful packet with grounded facts separated from assumptions.
- [x] 1.2 Implement a normalization service module that reads uploaded markdown, calls the configured LLM client, and returns normalized packet, normalization report, and builder narrative outputs.
- [x] 1.3 Add fail-closed output validation so malformed model output cannot be treated as a successful normalized packet.

## 2. Artifact Persistence and Contract Alignment

- [x] 2.1 Extend `utils/toolkit_homebrew_upload_contract.py` to persist and validate full normalization artifacts rather than placeholder-only packet state.
- [x] 2.2 Ensure normalization-required uploads only become review-ready after `normalized_packet.json`, `normalization_report.json`, and `builder_narrative.txt` are all persisted successfully.

## 3. Upload Job Orchestration

- [x] 3.1 Update `web/routes/toolkit_homebrew_routes.py` so normalization-required uploads enter `normalizing` and invoke the normalization service asynchronously.
- [x] 3.2 Transition jobs to `awaiting_review` only after successful normalization persistence, and surface actionable failure payloads when provider or parse steps fail.
- [x] 3.3 Preserve current deterministic-ready upload behavior and concept-builder behavior without forcing those paths through the normalizer.

## 4. Toolkit Reporting Surface

- [x] 4.1 Update `web/templates/module_toolkit.html` reporting logic to show `normalizing` distinctly from `awaiting_review`.
- [x] 4.2 Ensure the existing review UI only loads after true normalization handoff rather than routing-only placeholder state.

## 5. Regression Coverage

- [x] 5.1 Add or extend service-level tests for source-faithful packet generation, assumption separation, and malformed output rejection.
- [x] 5.2 Extend toolkit upload job tests for `normalizing` -> `awaiting_review` transitions, provider/persistence failure handling, and no-regression deterministic-ready behavior.

## 6. Verification

- [x] 6.1 Run targeted syntax validation for modified Python files and any JS-bearing template logic touched by normalization-state reporting.
- [x] 6.2 Run targeted regression tests for the normalization service and toolkit upload route/job state changes.
- [x] 6.3 Run `openspec validate toolkit-homebrew-normalization-engine`.

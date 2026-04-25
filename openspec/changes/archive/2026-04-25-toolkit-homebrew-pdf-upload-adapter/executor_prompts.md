# Executor Prompts - toolkit-homebrew-pdf-upload-adapter

---

## Execution Contract

- MUST execute in order: task groups 2 -> 7. OpenSpec contract tasks are already drafted for review.
- MUST keep the existing Markdown ingest pipeline source path as a text/Markdown file.
- MUST NOT pass raw PDF bytes to `run_ingest_pipeline(...)`, `assess_source_readiness(...)`, or the normalizer.
- MUST preserve current `.md` upload behavior and staged rebuild confirmation semantics.
- MUST keep host file edits minimal and mark required hooks with `# TABLETOP MODE:` where host-file integration needs it.
- MUST keep Python-visible text ASCII only.
- MUST NOT add OCR, image extraction, map extraction, or LLM-native PDF parsing in this change.
- MUST NOT commit or push changes.

---

## Prompt 1 - PDF Conversion Helper

Implement tasks 2.1-2.3 only.

Scope:
- Add a small helper under `utils/` or `web/extensions/` for PDF-to-Markdown conversion.
- Add direct unit tests for the helper if practical.

Requirements:
- Use the existing `pypdf` dependency; do not add a new package.
- Extract page text with deterministic page order.
- Write generated Markdown with a short conversion header and `## PDF Page N` markers.
- Write or return a structured report with: status, source filename, source PDF path, output Markdown path, SHA-256, byte size, extractor, page count, pages with text, extracted chars, minimum required chars, warnings, and error message when applicable.
- Fail closed for unreadable, encrypted, no-text, or too-little-text PDFs. Use a deterministic minimum-text rule.
- Do not call the existing ingest pipeline from this helper.

Edit Strategy:
- Apply one anchored patch at a time, then run py_compile before the next Python patch.
- Avoid broad regex or script rewrites.

Verify before moving on:
- `.venv/bin/python -m py_compile <new_converter_module> [new tests if added]`
- `.venv/bin/python <new_or_existing_converter_test>` if a focused test is added.

---

## Prompt 2 - Upload Route Adapter

Implement tasks 3.1-3.4 only.

Scope:
- `web/routes/toolkit_homebrew_routes.py`
- `utils/toolkit_homebrew_upload_contract.py` only if first-class artifact keys are needed.
- PDF converter helper from Prompt 1.

Requirements:
- Expand backend accepted extensions to `.md` and `.pdf`.
- Keep `.md` behavior unchanged: uploaded Markdown still becomes canonical `source_original.md` and starts the same job flow.
- For `.pdf`, save raw PDF bytes to an additive provenance path, convert to canonical `source_original.md`, write `pdf_conversion_report.json`, and start `_run_homebrew_ingest_job(...)` with the converted Markdown path.
- Keep job `source_path` as the Markdown/text path. Add `source_kind`, original PDF path, and conversion report metadata as additive job fields.
- If conversion fails, return a clear structured error before pipeline invocation and do not leave an active ingest job running.
- Update user-visible rejection wording to accepted `.md or .pdf` source types.

Edit Strategy:
- Apply one anchored patch at a time in `toolkit_homebrew_routes.py`.
- After each Python host-file edit, run py_compile before continuing.
- Do not refactor unrelated route/job lifecycle code.

Verify before moving on:
- `.venv/bin/python -m py_compile web/routes/toolkit_homebrew_routes.py utils/toolkit_homebrew_upload_contract.py <converter_module>`
- Source-level or focused test check proving PDF branch passes converted `.md` path to the worker/pipeline.

---

## Prompt 3 - Artifact Manifest Integration

Implement tasks 4.1-4.3 only.

Scope:
- `utils/toolkit_homebrew_upload_contract.py`
- `web/routes/toolkit_homebrew_routes.py` only for job payload/status exposure needed by artifact visibility.
- Tests that assert artifact manifest behavior.

Requirements:
- Preserve all existing artifact keys and their absent-safe behavior.
- Add additive PDF keys such as `source_upload_original_pdf` and `pdf_conversion_report` if using first-class manifest keys.
- Markdown-only jobs must show PDF artifacts as absent or omit PDF-specific job metadata without breaking existing consumers.
- PDF jobs must surface conversion artifact existence, paths, and sizes through the same artifact visibility contract or equivalent job-status metadata.

Verify before moving on:
- `.venv/bin/python -m py_compile utils/toolkit_homebrew_upload_contract.py web/routes/toolkit_homebrew_routes.py`
- Run focused artifact-manifest/upload status tests.

---

## Prompt 4 - Toolkit UI Copy And Client Validation

Implement tasks 5.1-5.3 only.

Scope:
- `web/templates/module_toolkit.html`

Requirements:
- Change upload title/copy from Markdown-only to `.md / .pdf` support.
- File input accept list must include `.md,.pdf,text/markdown,application/pdf`.
- Frontend no-file and bad-extension messages must describe `.md` or `.pdf`.
- Button text should be generic, for example `Import Homebrew Module`.
- Add warning copy that PDFs are text-extracted and image-only/OCR-needed PDFs are unsupported in this MVP.
- Preserve concept-builder controls and unrelated toolkit UI behavior.

Verify before moving on:
- Run inline JS syntax validation for the extracted script block if the template JS was touched.
- Run focused UI source-contract tests if present or added.

---

## Prompt 5 - Regression Coverage

Implement tasks 6.1-6.5 only.

Scope:
- `scripts/test_toolkit_homebrew_md_upload_routes.py` or a new focused upload/PDF adapter test file.
- UI source-contract tests under `scripts/` if existing pattern supports it.

Requirements:
- Update `.txt` rejection test to expect `.md or .pdf` wording.
- Add `.md` non-regression coverage for canonical source path and existing lifecycle.
- Add PDF happy-path coverage for raw PDF artifact, generated Markdown, conversion report, source kind metadata, and pipeline handoff path.
- Add failure coverage for no-text or converter failure, proving pipeline/worker is not invoked.
- Add UI source-contract coverage for accept list, copy, and frontend extension validation.

Verify before moving on:
- `.venv/bin/python -m py_compile <all touched test files>`
- `.venv/bin/python <focused_upload_pdf_tests>`

---

## Prompt 6 - Final Verification

Implement task group 7.x only.

Required final commands:
- `.venv/bin/python -m py_compile [all modified Python files for this change]`
- `.venv/bin/python scripts/test_toolkit_homebrew_md_upload_routes.py` or the focused replacement test suite.
- Run the focused UI source-contract test if separate.
- Run inline JS syntax validation for `web/templates/module_toolkit.html` if touched.
- `openspec validate toolkit-homebrew-pdf-upload-adapter`

Manual review checklist:
1. Confirm `.md` upload behavior remains unchanged.
2. Confirm `.pdf` upload writes raw PDF provenance separately from `source_original.md`.
3. Confirm `source_original.md` is readable Markdown after PDF conversion.
4. Confirm downstream job `source_path` points to Markdown, never the raw PDF.
5. Confirm image-only/OCR-needed PDFs fail clearly before ingest.

---

## Notes for Implementer

- Keep this slice narrow: it is a source adapter, not a semantic PDF understanding feature.
- The existing normalizer should continue doing source interpretation after conversion.
- Do not widen accepted upload types beyond `.md` and `.pdf` unless the OpenSpec contract is updated first.

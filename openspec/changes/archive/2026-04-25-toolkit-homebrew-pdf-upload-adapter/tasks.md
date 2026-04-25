# Tasks: toolkit-homebrew-pdf-upload-adapter

## 1. OpenSpec Contract

- [x] 1.1 Add delta requirements for `.md` plus `.pdf` toolkit upload acceptance while preserving Markdown pipeline handoff.
- [x] 1.2 Add PDF conversion capability requirements covering provenance, extraction report, failure semantics, and MVP non-goals.
- [x] 1.3 Add artifact-visibility requirements for additive PDF conversion artifacts.

## 2. PDF Conversion Helper

- [x] 2.1 Add a small conversion helper using existing `pypdf` that reads a PDF, extracts page text, normalizes basic extraction artifacts, and writes generated Markdown.
- [x] 2.2 Compute deterministic conversion metadata: SHA-256, byte size, page count, pages with text, extracted character count, warnings, and output path.
- [x] 2.3 Fail closed with structured errors for unreadable, encrypted, no-text, or too-little-text PDFs before pipeline invocation.

## 3. Upload Route Adapter

- [x] 3.1 Expand toolkit upload extension validation and user-visible rejection wording from Markdown-only to `.md` or `.pdf`.
- [x] 3.2 Preserve existing `.md` behavior, including canonical `source_original.md`, job states, and overwrite confirmation flow.
- [x] 3.3 For `.pdf`, save raw PDF provenance separately, write converted Markdown to canonical `source_original.md`, write `pdf_conversion_report.json`, and start the existing ingest job with the Markdown path.
- [x] 3.4 Record source kind and conversion metadata in job payload/status without breaking existing job consumers.

## 4. Artifact Visibility

- [x] 4.1 Add additive workspace artifact keys for raw PDF provenance and PDF conversion report, or otherwise expose equivalent conversion metadata in job status.
- [x] 4.2 Ensure `artifact_manifest` continues listing all pre-existing artifact keys for every upload workspace.
- [x] 4.3 Ensure PDF conversion artifacts appear in artifact visibility when present and are absent-safe when the job is Markdown-only.

## 5. Toolkit UI

- [x] 5.1 Update upload section copy, file input accept list, no-file error, extension validation, and button label for `.md / .pdf` support.
- [x] 5.2 Add user-facing warning text that PDFs are text-extracted and image-only/OCR-needed PDFs are not supported in this MVP.
- [x] 5.3 Preserve the existing concept-builder UI and all non-upload toolkit controls.

## 6. Regression Coverage

- [x] 6.1 Update existing upload route tests so `.txt` remains rejected and the message describes `.md` or `.pdf`.
- [x] 6.2 Add Markdown non-regression tests proving `.md` upload still writes canonical `source_original.md` and uses the existing pipeline path.
- [x] 6.3 Add PDF happy-path tests proving raw PDF provenance, generated `source_original.md`, conversion report, source-kind metadata, and pipeline handoff path.
- [x] 6.4 Add PDF failure tests proving no-text/extraction-failure PDFs fail clearly and do not invoke the pipeline.
- [x] 6.5 Add UI source-contract tests for upload copy, accept attribute, and frontend extension validation.

## 7. Verification

- [x] 7.1 Run Python compile checks for all touched Python files.
- [x] 7.2 Run targeted upload route/converter/UI tests added or updated in this change.
- [x] 7.3 Run `openspec validate toolkit-homebrew-pdf-upload-adapter`.
- [x] 7.4 Manually review that raw PDFs never flow into text-reader pipeline calls.

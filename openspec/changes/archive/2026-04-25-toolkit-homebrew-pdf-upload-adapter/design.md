# Design: toolkit-homebrew-pdf-upload-adapter

## Overview

Add a pre-pipeline upload adapter for PDF sources. The adapter branches at upload time, before the existing Homebrew ingest job starts:

- `.md` uploads keep the current behavior and save directly to the canonical workspace source file.
- `.pdf` uploads save the raw PDF as provenance, extract text with `pypdf`, write converted Markdown to the canonical workspace source file, write a conversion report, then start the existing ingest job using the canonical Markdown source path.

This keeps the established Markdown pipeline as the only downstream source contract.

## Existing Contracts To Preserve

- `web/routes/toolkit_homebrew_routes.py` currently starts `_run_homebrew_ingest_job(job_id, source_path, workspace, source_rights_class)`.
- `_run_shared_ingest_pipeline(...)` ultimately calls `scripts.homebrew_ingest_dev.run_ingest_pipeline(...)` with the source path.
- `scripts/homebrew_preflight.py` and `utils/toolkit_homebrew_normalizer.py` call `Path.read_text(...)` on that source path.
- `utils/toolkit_homebrew_upload_contract.py` currently exposes `source_original` as `workspace / "source_original.md"`.

The adapter MUST NOT pass raw PDF bytes into these text-reader paths.

## Proposed Flow

1. Upload route validates extension against `.md` and `.pdf`.
2. Route creates the normal artifact workspace and placeholders.
3. For `.md`:
   - Save upload to `workspace_files["source_original"]`.
   - Start `_run_homebrew_ingest_job(...)` exactly as today.
4. For `.pdf`:
   - Save upload to an additive provenance path, for example `workspace / "source_upload_original.pdf"`.
   - Extract text page-by-page using `pypdf.PdfReader`.
   - Normalize only basic extraction noise: line endings, repeated whitespace, replacement/control characters that are unsafe for Markdown, and repeated blank lines.
   - Write generated Markdown to `workspace_files["source_original"]`.
   - Write `pdf_conversion_report.json`.
   - Start `_run_homebrew_ingest_job(...)` using the generated Markdown path.

## Conversion Output Shape

The generated Markdown SHOULD be deliberately simple:

```markdown
# <derived filename title>

> Converted from PDF upload for toolkit Homebrew ingest.
> Original file: <safe original filename>
> Extractor: pypdf

## PDF Page 1

<extracted text>

## PDF Page 2

<extracted text>
```

The normalizer remains responsible for semantic module interpretation; the PDF adapter only provides readable source text.

## Conversion Report

`pdf_conversion_report.json` MUST be structured and deterministic enough for tests and support:

- `status`: `success` or `error`
- `source_filename`
- `source_pdf_path`
- `converted_markdown_path`
- `sha256`
- `size_bytes`
- `extractor`: `pypdf`
- `page_count`
- `pages_with_text`
- `extracted_chars`
- `min_required_chars`
- `warnings`
- `error_message` when applicable

## Failure Semantics

Fail closed before pipeline invocation when:

- `pypdf` cannot import or cannot read the PDF.
- The PDF is encrypted or otherwise unreadable.
- No pages contain extractable text.
- Extracted text is below the deterministic minimum threshold.

The error message should explain that the MVP supports text-extractable PDFs and not image-only/OCR-needed PDFs.

## Artifact Manifest

Existing artifact keys MUST remain present. Additive keys MAY be introduced for:

- `source_upload_original_pdf`
- `pdf_conversion_report`

These keys should appear in `artifact_manifest` if the shared artifact contract is extended. If the implementation keeps them outside the shared known-key helper, the job payload still MUST surface conversion metadata clearly enough for tests and operator support.

## UI Contract

Update the upload surface to avoid promising OCR or full media ingestion:

- Title: `Homebrew Upload (.md / .pdf)`
- Accept list: `.md,.pdf,text/markdown,application/pdf`
- Button: `Import Homebrew Module`
- Warning copy: PDFs are text-extracted; scanned/image-only PDFs and map art extraction are not supported in this MVP.

## Testing Strategy

- Route tests for allowed/rejected extensions.
- Direct converter unit tests with a minimal generated PDF fixture if practical.
- Pipeline handoff tests using monkeypatched worker/pipeline start to confirm the source path is the converted Markdown path.
- No-text or extraction-failure PDF tests to confirm no job/pipeline starts.
- UI source-contract tests for copy, accept attributes, and frontend extension checks.

## Open Questions

- Exact minimum text threshold can be tuned during implementation. The contract only requires deterministic failure for no-text or too-little-text PDFs.
- Whether conversion artifacts should be added to `get_workspace_files(...)` as first-class known keys or surfaced only in job metadata. First-class keys are preferred for artifact visibility consistency.

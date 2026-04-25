# toolkit-homebrew-pdf-upload-adapter

## Why

The toolkit Homebrew uploader now works well for deterministic Markdown builds, but many DM Guild and community modules arrive as PDFs. Operators should be able to upload a typical adventure PDF without waiting for LLM-native PDF understanding or a separate manual conversion step.

The existing ingest, preflight, normalization, and packet-build pipeline already expects a readable Markdown/text source path. A narrow PDF adapter can preserve that pipeline by extracting PDF text into a canonical Markdown artifact first, then handing that artifact to the existing Markdown ingest flow.

## What Changes

### Modified Capabilities

- `toolkit-homebrew-md-upload` SHALL accept `.md` and `.pdf` sources from the toolkit upload surface.
- `toolkit-homebrew-md-upload` SHALL keep the shared ingest pipeline source path as a Markdown/text file for both raw Markdown uploads and converted PDF uploads.
- `toolkit-homebrew-artifact-visibility` SHALL expose additive PDF provenance and conversion artifacts without removing existing artifact keys.

### Added Capabilities

- `toolkit-pdf-source-conversion` SHALL convert accepted PDF uploads into deterministic Markdown before the ingest pipeline is invoked.

## Capability Scope

### MUST

- PDF uploads MUST be converted before `run_ingest_pipeline(...)`, `assess_source_readiness(...)`, or the normalizer reads the source path.
- The downstream `source_path` passed into the existing ingest job MUST remain the canonical Markdown pipeline input, currently the workspace `source_original.md` artifact.
- Raw PDF bytes MUST be preserved as an additive provenance artifact in the upload workspace.
- PDF conversion MUST write a structured conversion report with original filename, byte size, SHA-256, page count, pages with extractable text, extracted character count, output Markdown path, extractor identity, warnings, and status.
- Unreadable PDFs, encrypted PDFs that cannot be extracted, and image-only or too-little-text PDFs MUST fail closed before pipeline invocation with a user-visible message.
- Existing `.md` upload behavior MUST remain compatible with the current staged upload and packet-build flow.
- Unsupported files, such as `.txt`, MUST still be rejected before ingest with an error describing accepted `.md` or `.pdf` source types.
- Python-visible user/operator text MUST remain ASCII-only.

### SHOULD

- The MVP should use the existing `pypdf` dependency rather than adding a new PDF package.
- Converted Markdown should include a short generated-source header and page markers so normalization can reason about document order.
- Conversion warnings should identify pages with no extractable text, because maps, handouts, and scanned pages are common in DM Guild PDFs.
- UI copy should clearly state that PDFs are text-extracted and image-only/OCR-needed PDFs are not supported in this slice.

## Non-Goals

- No OCR implementation.
- No image, map, handout, or cover-art extraction from PDFs.
- No LLM-native PDF ingestion.
- No changes to module packet normalization semantics beyond receiving converted Markdown as input.
- No changes to watcher-folder ingest behavior unless existing shared constants require a narrow wording update.
- No concept-builder workflow changes.

## Impact

- Affected code:
  - `web/routes/toolkit_homebrew_routes.py`
  - `utils/toolkit_homebrew_upload_contract.py`
  - optional new helper under `utils/` or `web/extensions/` for PDF conversion
  - `web/templates/module_toolkit.html`
  - targeted regression tests under `scripts/`
- Affected workflows:
  - toolkit Homebrew upload jobs
  - artifact manifest/reporting for upload workspaces
  - operator-facing module uploader copy and validation

## Risks

- PDF text extraction can produce broken layout, hyphenation artifacts, or missing text.
- Image-heavy PDFs may extract too little text and must fail clearly instead of sending garbage to normalization.
- Saving raw PDF bytes to `source_original.md` by accident would break downstream text readers.
- Adding artifact keys incorrectly could regress existing artifact-manifest expectations.

## Fallback

- If PDF conversion fails, fail the upload before pipeline start and leave no active ingest job running.
- If optional conversion-report artifact registration fails after conversion succeeded, continue with the converted Markdown only if existing artifact visibility still reports the canonical source and log degraded metadata.
- Operators can still convert PDFs manually to Markdown and upload `.md` if the PDF adapter rejects an image-only source.

## Compatibility

- Existing Markdown upload jobs remain the primary path and should preserve current job states and rebuild confirmation semantics.
- The shared ingest pipeline, normalizer, packet builder, readiness gates, and finisher continue consuming a Markdown/text `source_path`.
- SP/MP gameplay compatibility is unaffected because this change only touches module-toolkit upload ingestion.

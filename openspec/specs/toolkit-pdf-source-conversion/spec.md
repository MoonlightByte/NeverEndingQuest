# toolkit-pdf-source-conversion Specification

## Purpose
TBD - created by archiving change toolkit-homebrew-pdf-upload-adapter. Update Purpose after archive.
## Requirements
### Requirement: PDF uploads convert to Markdown before ingest
The toolkit MUST treat PDF upload support as a deterministic pre-pipeline source adapter. Raw PDF bytes MUST NOT be passed to downstream source-readiness, normalization, or ingest functions that expect text.

#### Scenario: PDF conversion writes canonical Markdown source
- **WHEN** a valid text-extractable PDF is uploaded
- **THEN** the toolkit MUST save the raw PDF as a provenance artifact
- **AND** MUST extract text from the PDF in page order
- **AND** MUST write generated Markdown to the canonical upload source path consumed by the existing ingest pipeline
- **AND** MUST invoke the existing pipeline with the generated Markdown path, not the raw PDF path.

#### Scenario: Conversion report records source provenance
- **WHEN** PDF conversion succeeds
- **THEN** the toolkit MUST write a structured conversion report
- **AND** the report MUST include original filename, byte size, SHA-256, page count, pages with extractable text, extracted character count, output Markdown path, extractor identity, warnings, and status.

#### Scenario: Image-only PDF fails before ingest
- **WHEN** a PDF has no extractable text or less than the deterministic minimum required text
- **THEN** the toolkit MUST fail the upload before pipeline invocation
- **AND** MUST return a user-visible message explaining that image-only or OCR-needed PDFs are unsupported in this MVP
- **AND** MUST NOT create a running ingest job for that source.

#### Scenario: PDF extraction failure does not poison Markdown pipeline
- **WHEN** PDF reading or extraction raises an error
- **THEN** the toolkit MUST fail the upload before pipeline invocation
- **AND** MUST NOT write raw PDF bytes to the canonical Markdown source path
- **AND** MUST preserve a structured error for operator troubleshooting when possible.

### Requirement: PDF adapter has bounded MVP scope
The toolkit PDF adapter MUST remain a text extraction layer and MUST NOT claim support for OCR, map-image extraction, handout extraction, or LLM-native PDF parsing in this change.

#### Scenario: Image-heavy pages are reported as warnings
- **WHEN** a PDF contains pages with no extractable text but enough total text to continue
- **THEN** the toolkit SHOULD include page-level warnings in the conversion report
- **AND** MUST continue using only extracted text for generated Markdown.

#### Scenario: UI communicates PDF limitations
- **WHEN** the toolkit upload UI offers PDF upload
- **THEN** the UI MUST inform operators that PDFs are text-extracted
- **AND** MUST state that image-only or OCR-needed PDFs are unsupported in this MVP.


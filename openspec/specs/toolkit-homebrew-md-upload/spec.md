# toolkit-homebrew-md-upload Specification

## Purpose
TBD - created by archiving change toolkit-homebrew-md-upload-ingest. Update Purpose after archive.
## Requirements
### Requirement: Toolkit can import Homebrew markdown directly
The toolkit MUST provide a first-class upload path for Homebrewery markdown files and MUST invoke module ingest without requiring the operator to place files in `modules/ingest/`.

#### Scenario: Valid markdown upload starts toolkit ingest
- **WHEN** the operator submits a valid `.md` source file from the toolkit UI
- **THEN** the toolkit MUST accept the file
- **AND** MUST start a direct ingest job using the shared ingest pipeline
- **AND** MUST NOT require the watcher to discover or process the file.

#### Scenario: Unsupported file type is rejected before ingest
- **WHEN** the operator uploads a non-markdown file type
- **THEN** the toolkit MUST reject the submission before pipeline invocation
- **AND** MUST return a user-visible validation error describing the accepted source type.

### Requirement: Toolkit upload flow preserves existing builder flow
Adding markdown upload MUST NOT break or replace the existing concept-based Module Builder workflow.

#### Scenario: Concept builder remains available
- **WHEN** the toolkit loads after the markdown upload feature is added
- **THEN** the existing concept-based Module Builder controls MUST remain available
- **AND** concept-driven builds MUST continue to use their existing generation path.


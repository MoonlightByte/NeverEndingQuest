## MODIFIED Requirements

### Requirement: Toolkit can import Homebrew markdown directly
The toolkit MUST provide a first-class upload path for Homebrewery markdown files and MUST start a direct toolkit-owned staged job without requiring the operator to place files in `modules/ingest/`.

#### Scenario: Valid markdown upload starts staged job
- **WHEN** the operator submits a valid `.md` source file from the toolkit UI
- **THEN** the toolkit MUST accept the file
- **AND** MUST start a direct staged upload job using the shared uploader or ingest pipeline surface
- **AND** MUST NOT require the watcher to discover or process the file.

#### Scenario: Review boundary is preserved after packet preparation
- **WHEN** a toolkit Homebrew upload job finishes packet preparation and requires operator review before build continuation
- **THEN** the toolkit MUST stop that job at an explicit review boundary
- **AND** MUST NOT treat upload completion as equivalent to build completion or registry-ready success.

#### Scenario: Unsupported file type is rejected before ingest
- **WHEN** the operator uploads a non-markdown file type
- **THEN** the toolkit MUST reject the submission before pipeline invocation
- **AND** MUST return a user-visible validation error describing the accepted source type.

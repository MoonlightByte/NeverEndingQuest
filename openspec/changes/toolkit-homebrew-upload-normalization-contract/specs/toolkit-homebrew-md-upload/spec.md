## MODIFIED Requirements

### Requirement: Toolkit can import Homebrew markdown directly
The toolkit MUST provide a first-class upload path for Homebrewery markdown files and MUST start a staged upload job that can route to deterministic ingest or normalization-required handling without requiring the operator to place files in `modules/ingest/`.

#### Scenario: Valid markdown upload starts staged job
- **WHEN** the operator submits a valid `.md` source file from the toolkit UI
- **THEN** the toolkit MUST accept the file
- **AND** MUST start a direct toolkit-owned upload job
- **AND** MUST NOT require the watcher to discover or process the file

#### Scenario: Readable markdown requiring normalization is preserved
- **WHEN** the operator uploads readable markdown that does not satisfy deterministic-ready preflight requirements
- **THEN** the toolkit MUST preserve the upload in its artifact workspace
- **AND** MUST surface a normalization-required routing outcome instead of returning a generic hard failure caused only by structure ambiguity

#### Scenario: Unsupported file type is rejected before upload job execution
- **WHEN** the operator uploads a non-markdown file type
- **THEN** the toolkit MUST reject the submission before the upload job proceeds
- **AND** MUST return a user-visible validation error describing the accepted source type

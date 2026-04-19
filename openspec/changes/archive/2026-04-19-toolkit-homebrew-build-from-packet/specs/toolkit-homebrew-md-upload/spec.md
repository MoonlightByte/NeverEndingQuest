## MODIFIED Requirements

### Requirement: Toolkit can import Homebrew markdown directly
The toolkit MUST provide a first-class upload path for Homebrewery markdown files and MUST support the reviewed upload lifecycle through explicit pre-build and build-start states without requiring the operator to place files in `modules/ingest/`.

#### Scenario: Valid markdown upload starts staged job
- **WHEN** the operator submits a valid `.md` source file from the toolkit UI
- **THEN** the toolkit MUST accept the file
- **AND** MUST start a direct staged upload job using the shared uploader or ingest pipeline surface
- **AND** MUST NOT require the watcher to discover or process the file.

#### Scenario: Normalization-required upload enters normalizing stage before review
- **WHEN** a toolkit Homebrew upload requires interpretation before review or build continuation
- **THEN** the toolkit MUST transition that job into an explicit `normalizing` stage
- **AND** MUST NOT expose it as review-ready until normalization has completed successfully.

#### Scenario: Approved upload requires explicit build start
- **WHEN** a toolkit Homebrew upload has been approved for build
- **THEN** the toolkit MUST preserve `approved_for_build` as a resumable state until the operator explicitly starts the build
- **AND** approval alone MUST NOT auto-start module generation.

#### Scenario: Unsupported file type is rejected before ingest
- **WHEN** the operator uploads a non-markdown file type
- **THEN** the toolkit MUST reject the submission before pipeline invocation
- **AND** MUST return a user-visible validation error describing the accepted source type.

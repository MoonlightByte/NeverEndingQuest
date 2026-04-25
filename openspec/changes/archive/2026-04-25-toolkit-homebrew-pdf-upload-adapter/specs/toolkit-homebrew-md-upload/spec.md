## MODIFIED Requirements

### Requirement: Toolkit can import Homebrew markdown directly
The toolkit MUST provide a first-class upload path for Homebrewery markdown files and text-extractable PDF adventure files, and MUST support the reviewed upload lifecycle through explicit pre-build and build-start states without requiring the operator to place files in `modules/ingest/`. PDF uploads MUST be converted into the same canonical Markdown/text source contract before the shared ingest pipeline is invoked.

#### Scenario: Valid markdown upload starts staged job
- **WHEN** the operator submits a valid `.md` source file from the toolkit UI
- **THEN** the toolkit MUST accept the file
- **AND** MUST start a direct staged upload job using the shared uploader or ingest pipeline surface
- **AND** MUST NOT require the watcher to discover or process the file
- **AND** MUST preserve the existing Markdown upload source-path behavior.

#### Scenario: Valid PDF upload starts staged job through converted Markdown
- **WHEN** the operator submits a text-extractable `.pdf` source file from the toolkit UI
- **THEN** the toolkit MUST accept the file
- **AND** MUST convert the PDF into the canonical Markdown pipeline source before invoking the shared ingest pipeline
- **AND** MUST start the same staged upload job flow used by Markdown uploads
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
- **WHEN** the operator uploads a source file that is neither `.md` nor `.pdf`
- **THEN** the toolkit MUST reject the submission before pipeline invocation
- **AND** MUST return a user-visible validation error describing the accepted `.md` or `.pdf` source types.

#### Scenario: Repeated upload does not silently reuse existing module directory
- **WHEN** an auto-started Homebrew upload resolves to a module slug that already exists on disk
- **THEN** the toolkit MUST pause before build execution
- **AND** MUST require explicit operator confirmation for the backup + clean rebuild flow
- **AND** MUST NOT silently proceed with overlay rebuild behavior.

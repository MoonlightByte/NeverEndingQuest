# module-ingest-watch-folder-automation Specification

## Purpose
TBD - created by archiving change module-ingest-watch-machine. Update Purpose after archive.
## Requirements
### Requirement: Ingest watcher MUST monitor the dedicated watch folder
The server ingest worker MUST monitor `modules/ingest/` for supported source files (`.md`, `.markdown`, `.txt`) and MUST skip unsupported extensions.

#### Scenario: Supported source file is dropped into watch folder
- **WHEN** a file with supported extension appears in `modules/ingest/`
- **THEN** the worker queues it for ingest processing

#### Scenario: Unsupported source file appears
- **WHEN** a file with disallowed extension appears in `modules/ingest/`
- **THEN** the worker ignores the file and logs skip reason

### Requirement: Ingest watcher SHALL apply file stability guard before processing
The watcher SHALL require a file signature (size + mtime) to remain unchanged over at least one polling interval before ingesting.

#### Scenario: File is still being copied
- **WHEN** size or mtime changes between consecutive scans
- **THEN** ingest is deferred and no processing starts

#### Scenario: File becomes stable
- **WHEN** size and mtime remain unchanged across the guard window
- **THEN** ingest processing begins for that file

### Requirement: Watcher startup MUST be fail-open for gameplay server
Watcher initialization failures MUST NOT block web server startup or gameplay operations.

#### Scenario: Watcher dependency error at startup
- **WHEN** watcher import/start raises exception
- **THEN** server startup continues and a warning is logged

#### Scenario: Watcher starts successfully
- **WHEN** watcher initializes without error
- **THEN** ingest polling begins and startup logs include watch/archive paths


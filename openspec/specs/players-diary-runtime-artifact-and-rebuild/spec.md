# players-diary-runtime-artifact-and-rebuild Specification

## Purpose
TBD - created by archiving change players-diary-append-markdown. Update Purpose after archive.
## Requirements
### Requirement: Confirmed players diary SHALL use gameplay runtime storage, not Local_Docs
The system SHALL store the confirmed players diary and its bookmark in gameplay/runtime storage paths rather than using `Local_Docs`.

#### Scenario: Local docs remain reference-only
- **WHEN** the players diary feature is implemented
- **THEN** any `Local_Docs` diary artifact used during planning or manual testing SHALL remain reference-only and SHALL NOT become the runtime storage path for the web GUI

#### Scenario: Runtime diary state is stored separately from journal source
- **WHEN** the confirmed players diary feature stores append progress
- **THEN** it SHALL store bookmark state in a separate runtime bookmark file rather than mutating `journal.json`

### Requirement: The Journal GUI SHALL render the confirmed players diary artifact directly
The web GUI SHALL render the confirmed players diary from the canonical markdown artifact rather than reconstructing the confirmed diary from DB summary rows.

#### Scenario: Confirmed diary route returns runtime artifact content
- **WHEN** the Journal GUI requests confirmed diary content
- **THEN** the backend SHALL return the canonical players diary artifact content for rendering

#### Scenario: Draft diary remains separate
- **WHEN** the Journal GUI renders diary surfaces
- **THEN** any retained draft/live-session diary surface SHALL remain separate from the confirmed players diary markdown artifact

### Requirement: The system SHALL support full rebuild repair mode
The system SHALL support a full rebuild mode that regenerates the complete confirmed players diary markdown artifact from all of `journal.json`.

#### Scenario: Rebuild replaces diary artifact atomically
- **WHEN** the full rebuild mode succeeds
- **THEN** it SHALL replace the canonical confirmed diary artifact atomically and set the bookmark to the latest journal entry index

#### Scenario: Rebuild is repair path rather than default update path
- **WHEN** normal confirmed diary updates occur
- **THEN** the system SHALL use append mode by default and SHALL reserve full rebuild mode for explicit repair, reset, or manual regeneration

### Requirement: Dependency-sensitive players diary commands SHALL use the project venv interpreter
All append, rebuild, and verification commands for the confirmed players diary SHALL use `.venv/bin/python` to ensure provider/runtime dependencies match the real application environment.

#### Scenario: Diary rebuild command uses venv interpreter
- **WHEN** a builder or operator runs players diary append/rebuild tooling
- **THEN** the documented command examples SHALL use `.venv/bin/python` instead of system `python3` for dependency-sensitive paths


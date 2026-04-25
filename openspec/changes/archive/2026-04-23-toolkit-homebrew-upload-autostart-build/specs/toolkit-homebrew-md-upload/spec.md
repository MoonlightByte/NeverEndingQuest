## MODIFIED Requirements

### Requirement: Toolkit imports Homebrew markdown directly into packet build flow

The toolkit SHALL accept a Homebrew markdown upload, run the shared ingest and normalization pipeline, and automatically advance a successful normalized packet into the packet build flow without requiring a separate review approval step.

#### Scenario: Successful markdown upload auto-starts packet build

- **WHEN** an operator uploads valid Homebrew markdown from the toolkit builder
- **AND** the shared ingest pipeline produces a normalized packet without fatal validation errors
- **THEN** the toolkit starts the packet build flow automatically
- **AND** the operator is not required to click a separate approve or start-build action

#### Scenario: Concept builder flow remains available

- **WHEN** the toolkit is used without a Homebrew markdown upload
- **THEN** the existing concept-based module builder flow remains available and unchanged

## MODIFIED Requirements

### Requirement: Toolkit Homebrew ingest reporting SHALL support single-console UX without losing structured state

The toolkit SHALL continue exposing structured shared-pipeline and build progression state while supporting a simplified single-console uploader experience.

#### Scenario: Console-friendly reporting spans upload through auto-start build

- **WHEN** a Homebrew upload progresses through normalization, auto-start build, or overwrite-confirmation wait states
- **THEN** job responses SHALL continue exposing authoritative `status` and `stage` fields
- **AND** the default uploader UX SHALL be able to render those transitions through one primary rolling console/readout surface

#### Scenario: Rebuild preparation remains visible without operator-first UI clutter

- **WHEN** an existing module collision triggers overwrite confirmation or backup/cleanup preparation
- **THEN** the reporting contract SHALL continue surfacing those states and related metadata
- **AND** the default user surface SHALL present them as concise console/status guidance rather than as multiple operator-oriented readout panes

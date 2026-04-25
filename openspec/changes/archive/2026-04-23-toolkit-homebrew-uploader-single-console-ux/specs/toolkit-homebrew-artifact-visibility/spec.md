## MODIFIED Requirements

### Requirement: Artifact visibility SHALL remain available while default uploader UX stays simplified

Toolkit job status responses SHALL preserve artifact and recovery metadata even when the normal uploader surface hides operator-facing controls.

#### Scenario: Simplified default surface preserves artifact-manifest compatibility

- **WHEN** a Homebrew uploader job returns status data
- **THEN** the response SHALL continue including top-level `artifact_manifest`
- **AND** the manifest SHALL continue exposing its expected artifact keys for runtime and tooling compatibility
- **AND** the response SHALL continue exposing `rebuild_eligible` and `cleanup_allowed`

#### Scenario: Artifact-backed recovery remains non-default

- **WHEN** artifact-backed retry or cleanup capabilities are available for a job
- **THEN** those capabilities MAY remain accessible for advanced or developer-oriented flows
- **BUT** the default user surface SHALL not present artifact-workspace inspection or recovery actions as primary uploader controls

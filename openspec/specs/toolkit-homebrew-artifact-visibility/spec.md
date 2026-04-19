# toolkit-homebrew-artifact-visibility Specification

## Purpose
TBD - created by archiving change toolkit-homebrew-artifact-persistence. Update Purpose after archive.
## Requirements
### Requirement: Artifact Manifest Field in Job Status Response

Job status responses MUST include an `artifact_manifest` field at the top level of the response JSON.

#### Scenario: GET job status returns full artifact manifest
- **WHEN** an operator queries the job status endpoint for any homebrew upload job
- **THEN** the response includes `artifact_manifest` as a top-level field
- **AND** the manifest covers all artifact keys with existence and size information

### Requirement: Artifact Key Enumeration

The manifest MUST list every known artifact key with its `exists` boolean and, when present, its `path` and `size_bytes`.

#### Scenario: All artifact keys appear in manifest
- **WHEN** `build_artifact_manifest` is called on a workspace
- **THEN** every artifact key is listed with `exists: true/false`
- **AND** present artifacts include `path` and `size_bytes`

#### Scenario: Missing artifact keys never omitted
- **WHEN** `build_artifact_manifest` is called on a workspace where some artifacts are absent
- **THEN** absent artifacts appear with `exists: false`
- **AND** no artifact key is omitted from the manifest

### Requirement: Artifact Keys List

The manifest MUST include these artifact keys: `source_original`, `normalized_packet`, `normalization_report`, `ui_review_snapshot`, `builder_input`, `build_result`, `readiness_validation_report`, `readiness_audit_report`, `repair_report`, `finishing_report`.

#### Scenario: All ten named artifact keys are present
- **WHEN** `build_artifact_manifest` is called
- **THEN** all 10 named artifact keys appear in the `artifacts` block

### Requirement: Rebuild Eligibility Block

The manifest MUST include a `rebuild_eligible` block showing `from_packet` and `from_finishing` boolean flags derived from artifact presence and job state.

#### Scenario: from_packet true when packet present and job terminal or user-requested
- **WHEN** a job has `normalized_packet` artifact present and is in a terminal state
- **THEN** `rebuild_eligible.from_packet` is `true`

#### Scenario: from_finishing true only when build artifacts present and readiness was run
- **WHEN** a job has `builder_input` and `build_result` present and has reached `ready_for_finishing`
- **THEN** `rebuild_eligible.from_finishing` is `true`

### Requirement: Cleanup Allowed Flag

The manifest MUST include a `cleanup_allowed` boolean.

#### Scenario: Cleanup allowed for terminal-state jobs
- **WHEN** a job is in `completed`, `not_publishable`, `quarantined`, or `failed` state
- **THEN** `cleanup_allowed` is `true`


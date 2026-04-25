## MODIFIED Requirements

### Requirement: Artifact Keys List
The manifest MUST include these artifact keys: `source_original`, `normalized_packet`, `normalization_report`, `ui_review_snapshot`, `builder_input`, `build_result`, `readiness_validation_report`, `readiness_audit_report`, `repair_report`, `finishing_report`. When PDF upload support is enabled, the manifest MUST also preserve additive visibility for raw PDF provenance and PDF conversion reporting artifacts without removing or renaming the existing keys.

#### Scenario: Existing named artifact keys remain present
- **WHEN** `build_artifact_manifest` is called
- **THEN** all pre-existing named artifact keys appear in the `artifacts` block
- **AND** existing consumers that depend on those keys continue to receive absent-safe entries.

#### Scenario: PDF conversion artifacts are visible for PDF jobs
- **WHEN** `build_artifact_manifest` is called for a workspace created from a PDF upload
- **THEN** the manifest MUST expose the raw PDF provenance artifact and conversion report artifact, or equivalent top-level job metadata
- **AND** present PDF artifacts MUST include path and size information when available.

#### Scenario: Markdown jobs remain absent-safe for PDF artifacts
- **WHEN** `build_artifact_manifest` is called for a workspace created from a Markdown upload
- **THEN** any PDF-specific artifact keys MUST be absent-safe
- **AND** Markdown-only jobs MUST NOT be treated as degraded because PDF artifacts are absent.

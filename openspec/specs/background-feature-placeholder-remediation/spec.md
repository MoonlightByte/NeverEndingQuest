## Purpose

Enable non-destructive detection and remediation of generic background feature placeholders in character files while preserving authored content and mechanical field integrity.

## Requirements

### Requirement: Generic background-feature placeholders SHALL be detected deterministically
The system SHALL classify configured generic placeholder values (for example `Feature`, `Background Feature`, `Standard background feature`, and equivalent baseline placeholders) as narrative-incomplete for remediation purposes.

#### Scenario: Placeholder detection on read-audit path
- **WHEN** character narrative quality checks inspect `backgroundFeature.name` and `backgroundFeature.description`
- **THEN** configured generic placeholder variants are flagged as generic placeholders

### Requirement: Remediation MUST update only generic placeholder values
Placeholder remediation operations MUST mutate only fields matching the generic-placeholder allowlist and MUST preserve all non-placeholder authored values.

#### Scenario: Mixed authored and generic values
- **WHEN** a character has authored `backgroundFeature.name` and generic placeholder description
- **THEN** remediation updates only the generic description and leaves authored name unchanged

#### Scenario: Fully authored values
- **WHEN** both background feature fields are authored and not placeholders
- **THEN** remediation performs no mutation

### Requirement: Remediation tooling SHALL support dry-run and fail-open execution
Bulk remediation tooling SHALL provide dry-run reporting before writes and SHALL fail open on per-file errors while continuing remaining files.

#### Scenario: Dry-run report
- **WHEN** remediation is executed in dry-run mode
- **THEN** the system reports planned file/field changes without writing character files

#### Scenario: File-level write failure
- **WHEN** one character file fails to load or write during apply mode
- **THEN** remediation logs the failure and continues processing remaining files

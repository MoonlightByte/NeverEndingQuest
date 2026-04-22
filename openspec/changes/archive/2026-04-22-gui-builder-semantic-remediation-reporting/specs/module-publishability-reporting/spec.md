# module-publishability-reporting Specification Delta

## ADDED Requirements

### Requirement: Toolkit reporting SHALL expose structured semantic blocker detail for remediation
When publication-facing toolkit reporting includes semantic blocker findings, it SHALL expose enough structured detail for operators to identify the blocker class and authored source without reading raw JSON only.

#### Scenario: Structured blocking findings reach toolkit reporting
- **GIVEN** publishability reporting contains `blocking_findings` for semantic blockers
- **WHEN** toolkit reporting is emitted or rendered
- **THEN** it SHALL surface the blocker class and message
- **AND** SHALL preserve relevant context such as unresolved phrase, candidate location IDs, or authored source when that context is present.

#### Scenario: Structured findings absent falls back safely
- **GIVEN** publishability reporting contains semantic blockers but no structured `blocking_findings`
- **WHEN** toolkit reporting is emitted or rendered
- **THEN** it SHALL fall back to `blocking_errors`
- **AND** SHALL still present a semantic remediation path rather than raw JSON only.

## SHOULD Guidance

- SHOULD keep semantic remediation wording general so it applies to any module surfaced by toolkit workflows.
- SHOULD keep media handoff guidance separate from semantic blocker guidance.

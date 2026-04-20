## MODIFIED Requirements

### Requirement: Toolkit builds run a shared post-build finishing pass
Toolkit-generated module directories MUST run a shared post-build finishing pass after raw generation succeeds so they do not bypass the quality stages already used by the ingest workflow.

#### Scenario: Successful raw build enters finishing pass
- **WHEN** `ModuleBuilder.build_module(...)` completes successfully for a toolkit build
- **THEN** the toolkit MUST run a post-build finishing pass before declaring the build fully complete

#### Scenario: Finishing pass reuses existing quality stages
- **WHEN** the toolkit runs its post-build finishing pass
- **THEN** the pass MUST include continuity normalization, semantic authority enrichment, registry verification, monster materialization, and publication evaluation or their shared wrappers
- **AND** MUST NOT require a duplicate reimplementation of those stages inside the toolkit transport layer

#### Scenario: Monster materialization stage reports direct helper outcome
- **WHEN** the finishing pass executes monster materialization
- **THEN** the stage result MUST come from direct helper execution outcome
- **AND** MUST NOT depend on parsing subprocess stderr/stdout to infer success or failure

## ADDED Requirements

### Requirement: Toolkit finishing SHALL declare source-aware readiness and publishability outcomes
Toolkit finishing MUST pass toolkit source identity into readiness and publishability evaluation so final reports reflect the correct provenance contract.

#### Scenario: Toolkit finisher evaluates publishability as toolkit source
- **WHEN** the toolkit finisher invokes readiness or publishability evaluation
- **THEN** it MUST declare the module source as toolkit
- **AND** the final report MUST preserve stage outcomes using toolkit-source semantics

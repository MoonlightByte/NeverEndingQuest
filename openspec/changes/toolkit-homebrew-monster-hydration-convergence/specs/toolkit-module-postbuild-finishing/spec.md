## MODIFIED Requirements

### Requirement: Toolkit builds run a shared post-build finishing pass
Toolkit-generated module directories MUST run a post-build finishing pass after raw generation succeeds so they do not bypass the quality stages already used by the ingest workflow.

#### Scenario: Successful raw build enters finishing pass
- **WHEN** `ModuleBuilder.build_module(...)` completes successfully for a toolkit build
- **THEN** the toolkit MUST run a post-build finishing pass before declaring the build fully complete.

#### Scenario: Finishing pass reuses existing quality stages
- **WHEN** the toolkit runs its post-build finishing pass
- **THEN** the pass MUST include continuity normalization, registry verification, and monster hydration or their shared wrappers
- **AND** MUST NOT require a duplicate reimplementation of those stages inside the toolkit transport layer.

#### Scenario: Finishing uses shared monster hydration convergence contract
- **WHEN** toolkit finishing encounters a missing monster stat file referenced by authored module content
- **THEN** finishing MUST route that resolution through the shared monster hydration contract used by readiness and runtime-authorized hydration
- **AND** MUST preserve structured hydration outcome details for reporting

## ADDED Requirements

### Requirement: Toolkit builds run a shared post-build finishing pass
Toolkit-generated module directories MUST run a post-build finishing pass after raw generation succeeds so they do not bypass the quality stages already used by the ingest workflow.

#### Scenario: Successful raw build enters finishing pass
- **WHEN** `ModuleBuilder.build_module(...)` completes successfully for a toolkit build
- **THEN** the toolkit MUST run a post-build finishing pass before declaring the build fully complete.

#### Scenario: Finishing pass reuses existing quality stages
- **WHEN** the toolkit runs its post-build finishing pass
- **THEN** the pass MUST include continuity normalization, registry verification, and monster materialization or their shared wrappers
- **AND** MUST NOT require a duplicate reimplementation of those stages inside the toolkit transport layer.

### Requirement: Finishing parity stops short of full semantic publication compliance
The first builder parity slice MUST improve publication readiness without claiming full semantic publication compliance.

#### Scenario: Full publication semantics remain out of scope
- **WHEN** a toolkit build completes its parity finishing pass
- **THEN** the result MUST NOT imply that probe-based semantic publication checks, spatial grounding, or tactical-grid generation have been completed unless a later change explicitly adds them.
